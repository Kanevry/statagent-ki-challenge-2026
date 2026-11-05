import { z } from "zod";

// Web-Form eines vorbereiteten Antrags (#35). `lotse antrag <art> --sitzung <id> --json` liefert den absoluten Pfad
// des erzeugten PDFs, die Formulardatei mit Hash und Quellen als „<Ordner>/<Datei>.pdf, S. <n>: „<Wortlaut>““.
// An den Browser geht nichts davon: kein `pdf`, keine `datei`, kein `sha256`, kein Pfad. Eine Quelle wird zu
// {seite, wortlaut}; die Seite zeigt sie als „Antrag PAL080, S. 2“ mit dem Wortlaut hinter „Beleg anzeigen“.
// Datei ohne Node-Abhängigkeit: Route, Seite und Replay nutzen dieselbe Abbildung.

/** Art des Antrags, wie sie die CLI als Argument bekommt (z. B. `pflegegeld`). */
export const ART_MUSTER = /^[a-z_]{2,32}$/;
/** Sitzungs-ID des Kerns (uuid4, klein geschrieben). Eng, weil sie Teil eines Dateinamens wird. */
export const UUID_MUSTER = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

/** Eingabe von POST /api/uc1/antrag. Meldungen sind eigene deutsche Sätze, nie Texte von zod. */
export const antragEingabeSchema = z.object({
  art: z.string("Die Art des Antrags fehlt.").regex(ART_MUSTER, "Die Art des Antrags ist ungültig."),
  sitzung: z.string("Die Sitzung fehlt.").regex(UUID_MUSTER, "Die Sitzung ist ungültig."),
});
export type AntragEingabe = z.infer<typeof antragEingabeSchema>;

const textOderNull = z.string().nullable().optional().transform((wert) => wert ?? null);

/** Rohe Ausgabe des Kerns, nur die Felder, die das Web braucht; `pdf`, `datei`, `sha256` fallen beim Parsen weg. */
export const rohAntragSchema = z.object({
  art: z.string().regex(ART_MUSTER),
  sitzung_id: z.string().min(1),
  formular: z.object({ bezeichnung: z.string(), version: textOderNull }),
  formularwahl: z.object({ begruendung: textOderNull, quelle: textOderNull }).nullable().optional(),
  befuellt: z.array(
    z.object({
      feld: z.string(),
      wert: z.string(),
      angaben: z.array(z.string()).default([]),
      seite: z.number().int().nullable().optional(),
    }),
  ),
  noch_offen: z.array(z.object({ id: z.string(), text: z.string(), quelle: textOderNull })),
  unterlagen: z.array(z.object({ text: z.string(), quelle: textOderNull, bedingung: textOderNull })).default([]),
  stelle: z
    .object({ name: z.string(), stelle: textOderNull, fundstelle: textOderNull, zitat: textOderNull })
    .nullable()
    .optional(),
  eingereicht: z.boolean(),
});
export type RohAntrag = z.infer<typeof rohAntragSchema>;

const belegSchema = z.object({ seite: z.number().int(), wortlaut: z.string() });
export type AntragBeleg = z.infer<typeof belegSchema>;

export const webAntragSchema = z.object({
  art: z.string(),
  sitzung_id: z.string(),
  /** Kurzname des Formulars, z. B. „Antrag PAL080“; steht vor jeder Seitenangabe. */
  kurz: z.string(),
  /** Code des Formulars ohne Wort davor, z. B. „PAL080“, oder `null`. */
  code: z.string().nullable(),
  bezeichnung: z.string(),
  begruendung: z.string().nullable(),
  begruendung_beleg: belegSchema.nullable(),
  befuellt: z.array(z.object({ feld: z.string(), wert: z.string() })),
  noch_offen: z.array(z.object({ id: z.string(), text: z.string(), beleg: belegSchema.nullable() })),
  unterlagen: z.array(z.object({ text: z.string(), bedingung: z.string().nullable(), beleg: belegSchema.nullable() })),
  stelle: z
    .object({ name: z.string(), kurz: z.string().nullable(), fundstelle: z.string().nullable(), zitat: z.string().nullable() })
    .nullable(),
  eingereicht: z.boolean(),
});
export type WebAntrag = z.infer<typeof webAntragSchema>;

/**
 * „Anträge und Formulare/PAL080.pdf, S. 2: „Gründe Ihrer Pflegebedürftigkeit:““ → {seite: 2, wortlaut: …}.
 * Der Pfad vor der Seite fällt weg. Ohne Seite oder Wortlaut gibt es keinen Beleg (`null`).
 */
export function parseQuelle(quelle: string | null | undefined): AntragBeleg | null {
  if (!quelle) return null;
  const treffer = /,\s*S\.\s*(\d+)\s*:\s*„([\s\S]+)“\s*$/.exec(quelle);
  if (!treffer?.[1] || !treffer[2]) return null;
  const wortlaut = treffer[2].trim();
  return wortlaut ? { seite: Number(treffer[1]), wortlaut } : null;
}

/** Code des Formulars aus der Bezeichnung („… (PAL080) der PVA“) oder der Version („PAL 080 (01. 2025)“). */
export function formularCode(bezeichnung: string, version?: string | null): string | null {
  for (const klammer of bezeichnung.matchAll(/\(([^()]+)\)/g)) {
    const inhalt = klammer[1]?.trim() ?? "";
    if (/^[A-ZÄÖÜ]{2,}[\s-]?\d{2,}[A-Za-z]?$/.test(inhalt)) return inhalt.replace(/[\s-]/g, "");
  }
  const ausVersion = version ? /^([A-ZÄÖÜ]{2,})[\s-]?(\d{2,})\b/.exec(version.trim()) : null;
  return ausVersion ? `${ausVersion[1]}${ausVersion[2]}` : null;
}

/** „Antrag PAL080“; ohne Code „Antrag“ (nie die lange Bezeichnung vor einer Seitenangabe). */
export function formularKurz(bezeichnung: string, version?: string | null): string {
  const code = formularCode(bezeichnung, version);
  return code ? `Antrag ${code}` : "Antrag";
}

/** Bezeichnungen der Formularfelder sind Kürzel aus dem PDF („Fam.Name“); bekannte Angaben bekommen ein Wort. */
const FELDNAMEN: Readonly<Record<string, string>> = {
  "person.familienname": "Familienname",
  "person.vorname": "Vorname",
  "person.geburtsdatum": "Geburtsdatum",
  "person.strasse": "Straße",
  "person.hausnummer": "Hausnummer",
  "person.plz": "Postleitzahl",
  "person.ort": "Ort",
};

/** Erster Buchstabe groß, Punkt am Ende: Texte des Kerns beginnen oft klein („ob Pflegegeld …“). */
export function alsSatz(text: string): string {
  const t = text.trim();
  if (!t) return t;
  const gross = t.charAt(0).toLocaleUpperCase("de-AT") + t.slice(1);
  return /[.!?]$/.test(gross) ? gross : `${gross}.`;
}

/** Rohe Kern-Ausgabe → Web-Form, oder `null`, wenn ein Pflichtfeld fehlt oder falsch ist. */
export function abbildenAntrag(roh: unknown): WebAntrag | null {
  const geprueft = rohAntragSchema.safeParse(roh);
  if (!geprueft.success) return null;
  const a = geprueft.data;
  const code = formularCode(a.formular.bezeichnung, a.formular.version);
  const stelleKurz = a.stelle?.stelle ?? null;
  return {
    art: a.art,
    sitzung_id: a.sitzung_id,
    kurz: code ? `Antrag ${code}` : "Antrag",
    code,
    bezeichnung: a.formular.bezeichnung,
    begruendung: a.formularwahl?.begruendung ?? null,
    begruendung_beleg: parseQuelle(a.formularwahl?.quelle),
    befuellt: a.befuellt.map(({ feld, wert, angaben }) => ({
      feld: (angaben[0] && FELDNAMEN[angaben[0]]) || feld,
      wert,
    })),
    noch_offen: a.noch_offen.map(({ id, text, quelle }) => ({ id, text: alsSatz(text), beleg: parseQuelle(quelle) })),
    unterlagen: a.unterlagen.map(({ text, quelle, bedingung }) => ({
      text: alsSatz(text),
      bedingung,
      beleg: parseQuelle(quelle),
    })),
    stelle: a.stelle
      ? { name: a.stelle.name, kurz: stelleKurz, fundstelle: a.stelle.fundstelle, zitat: a.stelle.zitat }
      : null,
    eingereicht: a.eingereicht,
  };
}

/** „7 Angaben stehen schon drin“ / „1 Angabe steht schon drin“. */
export function antragUnterzeile(antrag: Pick<WebAntrag, "code" | "befuellt" | "noch_offen">): string {
  const drin = antrag.befuellt.length;
  const offen = antrag.noch_offen.length;
  const teil1 =
    drin === 0 ? "Noch steht keine Angabe drin" : drin === 1 ? "1 Angabe steht schon drin" : `${drin} Angaben stehen schon drin`;
  const teil2 = offen === 0 ? "Sie müssen nichts ergänzen" : offen === 1 ? "1 Punkt ergänzen Sie selbst" : `${offen} Punkte ergänzen Sie selbst`;
  const formular = antrag.code ? `Im Formular (${antrag.code}): ` : "";
  return `${formular}${teil1}, ${teil2}.`;
}

export type OffenerPunkt = WebAntrag["noch_offen"][number];
export type OffeneGruppe = {
  /** Formularseite, `null` für Punkte ohne Beleg. */
  seite: number | null;
  /** Nummer des ersten Punkts der Gruppe; die Nummerierung läuft über alle Gruppen durch. */
  start: number;
  punkte: OffenerPunkt[];
  /** Ein Beleg je Gruppe: Wortlaute der Seite, jeder nur einmal. */
  wortlaut: string | null;
};

/**
 * Offene Punkte nach Formularseite (Urteil ui-regie-32: eine Gruppe je Seite, ein Herkunft-Chip je Gruppe statt je
 * Punkt). Seiten aufsteigend, Punkte ohne Beleg zuletzt; innerhalb einer Seite bleibt die Reihenfolge des Kerns.
 */
export function offenNachSeite(punkte: readonly OffenerPunkt[]): OffeneGruppe[] {
  const nachSeite = new Map<number | null, OffenerPunkt[]>();
  for (const p of punkte) {
    const seite = p.beleg?.seite ?? null;
    nachSeite.set(seite, [...(nachSeite.get(seite) ?? []), p]);
  }
  const seiten = [...nachSeite.keys()].sort((a, b) => (a ?? Number.POSITIVE_INFINITY) - (b ?? Number.POSITIVE_INFINITY));
  let start = 1;
  return seiten.map((seite) => {
    const gruppe = nachSeite.get(seite) ?? [];
    const wortlaute = [...new Set(gruppe.flatMap((p) => (p.beleg ? [p.beleg.wortlaut] : [])))];
    const eintrag = { seite, start, punkte: gruppe, wortlaut: wortlaute.length > 0 ? wortlaute.join(" · ") : null };
    start += gruppe.length;
    return eintrag;
  });
}
