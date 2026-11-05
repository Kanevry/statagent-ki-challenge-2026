import { z } from "zod";

// Web-Form einer Lotse-Antwort (#35). `lotse frage --json` liefert die Dataclass `LotseAntwort` mit Volltext der
// Treffer, Deckungswerten und verworfenen Aussagen; an den Browser geht nur, was die Seite zeigt. Datei ohne
// Node-Abhängigkeit: Route (Abbildung) und Seite (Prüfung der Antwort, Replay) nutzen dieselben Schemas.

export const MAX_TEXT = 1000;
export const VERHALTEN = ["antwort", "abstinenz", "uebergabe", "rueckfrage"] as const;
export type Verhalten = (typeof VERHALTEN)[number];

/** Eingabe von POST /api/uc1/frage. Meldungen sind eigene deutsche Sätze, nie Texte von zod. */
export const frageSchema = z.object({
  text: z
    .string()
    .trim()
    .min(1, "Bitte schreiben Sie kurz, was los ist.")
    .max(MAX_TEXT, `Bitte höchstens ${MAX_TEXT} Zeichen.`),
  sitzung: z.uuid("Die Sitzung ist ungültig.").optional(),
  stil: z.enum(["standard", "einfach"], "Der Stil ist ungültig.").default("standard"),
  sprache: z.enum(["de", "en"], "Die Sprache ist ungültig.").optional(),
});
export type FrageEingabe = z.infer<typeof frageSchema>;

const textOderNull = z.string().nullable().optional().transform((wert) => wert ?? null);

/** Aussage im Rohformat des Kerns; `treffer`, `deckung` und alles Unbekannte fallen beim Parsen weg. */
const rohAussageSchema = z.object({
  text: z.string(),
  zitat: z.string(),
  schluessel: z.string(),
  stand: textOderNull,
  betrag: z.boolean().default(false),
  hinweis_hoehe: z.boolean().default(false),
  angebot: z.boolean().default(false),
});

/** Ausgabe von `lotse frage --json` (asdict von `LotseAntwort`), nur die Felder, die das Web braucht. */
export const rohAntwortSchema = z.object({
  text: z.string(),
  verhalten: z.enum(VERHALTEN),
  sitzung_id: z.string().min(1),
  aussagen: z.array(rohAussageSchema),
  rueckfrage: textOderNull,
  traeger: z.array(z.record(z.string(), z.string())).default([]),
  naechste_schritte: z.array(z.string()).default([]),
  leistungen: z.array(z.string()).default([]),
  antraege: z.array(z.string()).default([]),
  modell: textOderNull,
  provider: textOderNull,
  grenze: z.boolean().default(false),
  uebergabe_an: textOderNull,
  hinweise: z.array(z.string()).default([]),
  /** Gleiche Reihenfolge wie `aussagen`; `quelle` ist die Kurzform der Fundstelle. */
  belege: z.array(z.object({ quelle: z.string().nullable().optional() }).loose()).default([]),
});

export const aussageSchema = z.object({
  text: z.string(),
  /** Wörtlich aus dem Abschnitt; der Kern prüft, dass es ein Teilstring ist. */
  zitat: z.string(),
  /** Fundstelle, z. B. „BPGG § 4“. */
  quelle: z.string(),
  /** ISO-Datum der Fassung oder `null`. */
  stand: z.string().nullable(),
  betrag: z.boolean(),
  hinweis_hoehe: z.boolean(),
  angebot: z.boolean(),
});
export type Aussage = z.infer<typeof aussageSchema>;

export const webAntwortSchema = z.object({
  text: z.string(),
  verhalten: z.enum(VERHALTEN),
  sitzung_id: z.string(),
  rueckfrage: z.string().nullable(),
  aussagen: z.array(aussageSchema),
  traeger: z.array(z.record(z.string(), z.string())),
  naechste_schritte: z.array(z.string()),
  leistungen: z.array(z.string()),
  antraege: z.array(z.string()),
  modell: z.string().nullable(),
  provider: z.string().nullable(),
  grenze: z.boolean(),
  uebergabe_an: z.string().nullable(),
  hinweise: z.array(z.string()),
});
export type WebAntwort = z.infer<typeof webAntwortSchema>;

/** Rohe Kern-Ausgabe → Web-Form, oder `null`, wenn ein Pflichtfeld fehlt oder falsch ist. */
export function abbilden(roh: unknown): WebAntwort | null {
  const geprueft = rohAntwortSchema.safeParse(roh);
  if (!geprueft.success) return null;
  const { aussagen, belege, ...rest } = geprueft.data;
  return {
    ...rest,
    aussagen: aussagen.map(({ schluessel, ...aussage }, i) => ({
      ...aussage,
      // `schluessel` ist bei PDF-Treffern ein Dateipfad; die Kurzform steht im Beleg derselben Stelle.
      quelle: quelleAnzeige(belege[i]?.quelle?.trim() || schluessel),
    })),
  };
}

/**
 * Quelle, wie sie auf der Seite steht: nie ein Pfad. „Anträge und Formulare/PAL080_2026.pdf, S. 5“ wird
 * „PAL080, S. 5“ (nur der Dateiname, ohne Endung und ohne lange Ziffernfolgen wie Datum oder Nummer).
 */
export function quelleAnzeige(quelle: string): string {
  if (!quelle.includes("/") && !/\.pdf\b/i.test(quelle)) return quelle;
  const ohnePfad = quelle.slice(quelle.lastIndexOf("/") + 1);
  const komma = ohnePfad.search(/,\s*S\.\s*\d/);
  const name = komma >= 0 ? ohnePfad.slice(0, komma) : ohnePfad;
  const seite = komma >= 0 ? ohnePfad.slice(komma) : "";
  const sauber = name
    .replace(/\.pdf$/i, "")
    .replace(/(^|[\s_-])\d{3,}(?=$|[\s_-])/g, "$1")
    .replace(/[_\s]+/g, " ")
    .replace(/(^[\s-]+|[\s-]+$)/g, "")
    .trim();
  return `${sauber || "Dokument"}${seite}`;
}

const W_WOERTER = /^(wer|wen|wem|wessen|was|wie|wo|wann|warum|weshalb|wieso|welche[rsnm]?|wohin|woher|wof(ü|ue)r|wozu|womit|wieviel)$/;
const PRAEPOSITIONEN = new Set(["von", "an", "bei", "mit", "für", "in", "ab", "seit", "zu", "um", "auf", "aus", "nach", "über", "unter", "durch", "gegen"]);

/** Passen „Ja / Nein / Weiß nicht“? Nur bei Fragen, die mit dem Verb beginnen („Bekommt sie …?“). */
export function jaNeinFrage(frage: string): boolean {
  const erstes = frage.trim().split(/\s+/)[0]?.toLowerCase().replace(/[^\p{L}]/gu, "") ?? "";
  if (!erstes) return false;
  return !W_WOERTER.test(erstes) && !PRAEPOSITIONEN.has(erstes);
}

/** „2026-05-20“ → „20.05.2026“; alles andere bleibt, wie es ist. */
export function formatStand(iso: string): string {
  const treffer = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return treffer ? `${treffer[3]}.${treffer[2]}.${treffer[1]}` : iso;
}

/** Name einer zuständigen Stelle aus einem Träger-Eintrag des Kerns. */
export function traegerName(eintrag: Readonly<Record<string, string>>): string {
  return eintrag.name ?? eintrag.stelle ?? Object.values(eintrag).join(", ");
}
