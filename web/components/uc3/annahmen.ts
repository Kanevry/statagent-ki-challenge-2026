import { lies, type Lesung, type Sql } from "./db";
import { istMonat, monatName } from "./monat";
import { berichtPfad, berichtslistePfad } from "./navigation";
import { alltag } from "./sprache";

// Annahmen als eigener Bereich (Raster Bereich 6). Zwei Nummernkreise, beide echt: F1 bis F10 liegen in meta.annahme
// und stehen in den Qualitätsberichten; A1 bis A13 sind die Herleitung der Zählung in docs/plan/uc3/annahmen.md.
// Ein Test hält die Kurznamen unten mit dem Dokument gleich.

export type AnnahmeZeile = {
  nr: string;
  rueckfrage: string | null;
  /** true: Es gibt eine Rückfrage, und die Fachabteilung hat sie noch nicht beantwortet. */
  wartet: boolean;
  regelName: string | null;
  lieferungen: readonly string[] | null;
  satz: string;
  begruendung: string;
};

export const SQL_ANNAHMEN = [
  "SELECT a.nr, a.rueckfrage, a.regel_name, a.lieferungen, a.satz, a.begruendung,",
  "       a.rueckfrage IS NOT NULL AND q.antwort IS NULL AS wartet",
  "  FROM meta.annahme a LEFT JOIN meta.rueckfrage q ON q.nr = a.rueckfrage",
  " ORDER BY substr(a.nr, 2)::int",
].join("\n");

/** A1 bis A13: Nummer und Kurzname wie in docs/plan/uc3/annahmen.md. */
export const HERLEITUNG: readonly { nr: string; name: string }[] = [
  { nr: "A1", name: "Volldubletten einmal zählen" },
  { nr: "A2", name: "Leere Merkmale sind „unbekannt“" },
  { nr: "A3", name: "ÖNACE-2003-Unterabschnitte nach C" },
  { nr: "A4", name: "Geburtsmonat 13" },
  { nr: "A5", name: "Unplausibles Alter" },
  { nr: "A6", name: "Spaltentausch BEGINN/ENDE" },
  { nr: "A7", name: "Abschnittswahl am Stichtag" },
  { nr: "A8", name: "Abrechnung „nicht gezählt“" },
  { nr: "A9", name: "Erstlieferung kein Vollabzug" },
  { nr: "A10", name: "Phantom-Doppelmeldungen" },
  { nr: "A11", name: "Ungültiges ENDE" },
  { nr: "A12", name: "Fortschreibung bei belegtem Lieferausfall" },
  { nr: "A13", name: "Ministeriums-Lieferung" },
];

/**
 * Wofür eine Annahme gilt, als Ziele zum Klicken: je Monat dessen Qualitätsbericht, ohne Monate die Liste aller Berichte.
 */
export function geltungLinks(lieferungen: readonly string[] | null): { text: string; pfad: string }[] {
  if (!lieferungen || lieferungen.length === 0) return [{ text: "alle Monate", pfad: berichtslistePfad() }];
  return lieferungen.map((m) => ({ text: istMonat(m) ? monatName(m) : m, pfad: `${berichtPfad(m)}#annahmen` }));
}

/**
 * Kopfsatz der Seite. Jede Annahme hat eine Begründung (Pflichtspalte in meta.annahme). Nur Annahmen mit offener Rückfrage
 * werden als offen genannt, die anderen nicht.
 */
export function annahmenKopf(anzahl: number, offen: number): string {
  const kopf = anzahl === 1 ? "1 Annahme, begründet." : `${anzahl} Annahmen, jede begründet.`;
  if (offen === 0) return kopf;
  return `${kopf} Zu ${offen} ${offen === 1 ? "ist eine Rückfrage" : "sind Rückfragen"} an die Fachabteilung offen.`;
}

export function leseAnnahmen(optionen?: { sql?: Sql | null }): Promise<Lesung<AnnahmeZeile[]>> {
  return lies(async (sql) => {
    const [{ da } = { da: false }] = await sql<
      { da: boolean }[]
    >`SELECT to_regclass('meta.annahme') IS NOT NULL AND to_regclass('meta.rueckfrage') IS NOT NULL AS da`;
    if (!da) return [];
    const zeilen = await sql.unsafe<
      {
        nr: string;
        rueckfrage: string | null;
        wartet: boolean;
        regel_name: string | null;
        lieferungen: string[] | null;
        satz: string;
        begruendung: string;
      }[]
    >(SQL_ANNAHMEN);
    return zeilen.map((z) => ({
      nr: z.nr,
      rueckfrage: z.rueckfrage,
      wartet: z.wartet,
      regelName: z.regel_name,
      lieferungen: z.lieferungen,
      satz: alltag(z.satz),
      begruendung: alltag(z.begruendung),
    }));
  }, optionen);
}
