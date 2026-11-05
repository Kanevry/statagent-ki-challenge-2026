import { z } from "zod";

// Web-Form einer Lotse-Antwort (#35). `lotse frage --json` liefert die Dataclass `LotseAntwort` mit Volltext der
// Treffer, Deckungswerten und verworfenen Aussagen; an den Browser geht nur, was die Seite zeigt. Datei ohne
// Node-Abhängigkeit: Route (Abbildung) und Seite (Prüfung der Antwort, Replay) nutzen dieselben Schemas.

export const MAX_TEXT = 1000;
/** Zahl mit Tausenderpunkt („1.000“), ohne Intl: de-AT trennt je nach ICU mit Leerzeichen. */
export function tausender(zahl: number): string {
  return String(zahl).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

export const VERHALTEN = ["antwort", "abstinenz", "uebergabe", "rueckfrage"] as const;
export type Verhalten = (typeof VERHALTEN)[number];

/** Eingabe von POST /api/uc1/frage. Meldungen sind eigene deutsche Sätze, nie Texte von zod. */
export const frageSchema = z.object({
  text: z
    .string()
    .trim()
    .min(1, "Bitte schreiben Sie kurz, was los ist.")
    .max(MAX_TEXT, `Bitte höchstens ${tausender(MAX_TEXT)} Zeichen.`)
    // Steuerzeichen (außer Zeilenumbruch und Tab) bricht der Kern sonst mit Exit ≠ 0 ab: das wäre 503 statt 400.
    // Die Steuerzeichen im Muster sind gewollt; \p{Cc} nähme Tab und Zeilenumbruch mit (Lint-Gate, Lead a7).
    // eslint-disable-next-line no-control-regex
    .refine((text) => !/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/.test(text), "Der Text enthält unlesbare Zeichen."),
  sitzung: z.uuid("Die Sitzung ist ungültig.").optional(),
  stil: z.enum(["standard", "einfach"], "Der Stil ist ungültig.").default("standard"),
  sprache: z.enum(["de", "en"], "Die Sprache ist ungültig.").optional(),
});
export type FrageEingabe = z.infer<typeof frageSchema>;

const textOderNull = z.string().nullable().optional().transform((wert) => wert ?? null);

/** Zuständige Stelle; nur diese Schlüssel gehen an den Browser, alles andere aus dem Kern fällt weg. */
export const traegerSchema = z.object({
  leistung: textOderNull,
  stelle: textOderNull,
  name: z.string().min(1),
  fundstelle: textOderNull,
  zitat: textOderNull,
});
export type Traeger = z.infer<typeof traegerSchema>;

/** Antwortknopf einer Rückfrage: `text` steht auf dem Knopf, `antwort` geht als Nachricht hinaus. */
export const rueckfrageOptionSchema = z.object({ text: z.string().min(1), antwort: z.string().min(1) });
export type RueckfrageOption = z.infer<typeof rueckfrageOptionSchema>;

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
  rueckfrage_optionen: z.array(rueckfrageOptionSchema).default([]),
  traeger: z.array(traegerSchema).default([]),
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
  /** Antwortknöpfe der Rückfrage; ältere Aufnahmen haben keine. */
  rueckfrage_optionen: z.array(rueckfrageOptionSchema).default([]),
  aussagen: z.array(aussageSchema),
  traeger: z.array(traegerSchema),
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

/** Erster Satz einer Rückfrage („Wer zahlt die Pension?“); der Rest erklärt nur, was die Knöpfe schon zeigen. */
export function ersterSatz(text: string): string {
  const treffer = /^.*?[?!.](?=\s|$)/s.exec(text.trim());
  return (treffer ? treffer[0] : text).trim();
}

const MONATE = ["Jänner", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];

/** „2015-01-01“ → „1. Jänner 2015“ (österreichische Monatsnamen); alles andere bleibt, wie es ist. */
export function formatStand(iso: string): string {
  const treffer = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  const monat = treffer ? MONATE[Number(treffer[2]) - 1] : undefined;
  return treffer && monat ? `${Number(treffer[3])}. ${monat} ${treffer[1]}` : iso;
}

/** Notrufnummern, die im Text als antippbarer Link stehen. */
export const NOTRUFE = ["1450", "144"] as const;

/** Zerlegt einen Text in Teile; Notrufnummern als eigene Teile (`tel`), jede Stelle genau einmal. */
export function telefonTeile(text: string): Array<{ text: string; tel?: string }> {
  const teile: Array<{ text: string; tel?: string }> = [];
  let rest = 0;
  for (const treffer of text.matchAll(/(?<![\d/.,])(1450|144)(?![\d/.,]\d|\d)/g)) {
    const start = treffer.index ?? 0;
    if (start > rest) teile.push({ text: text.slice(rest, start) });
    teile.push({ text: treffer[0], tel: treffer[0] });
    rest = start + treffer[0].length;
  }
  if (rest < text.length) teile.push({ text: text.slice(rest) });
  return teile;
}

/** Name einer zuständigen Stelle aus einem Träger-Eintrag des Kerns. */
export function traegerName(eintrag: Pick<Traeger, "name" | "stelle">): string {
  return eintrag.name || eintrag.stelle || "";
}
