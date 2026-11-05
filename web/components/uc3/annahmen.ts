import { lies, type Lesung, type Sql } from "./db";
import { istMonat, monatName } from "./monat";
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
};

export const SQL_ANNAHMEN = [
  "SELECT a.nr, a.rueckfrage, a.regel_name, a.lieferungen, a.satz,",
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

/** „gilt für alle Monate“ oder „gilt für Mai 2025 und Februar 2026“. */
export function geltungSatz(lieferungen: readonly string[] | null): string {
  if (!lieferungen || lieferungen.length === 0) return "gilt für alle Monate";
  const namen = lieferungen.map((m) => (istMonat(m) ? monatName(m) : m));
  const letzter = namen[namen.length - 1]!;
  return `gilt für ${namen.length > 1 ? `${namen.slice(0, -1).join(", ")} und ${letzter}` : letzter}`;
}

/** Kopfsatz der Seite. Nur Annahmen mit offener Rückfrage warten auf die Fachabteilung, die anderen nicht. */
export function annahmenKopf(anzahl: number, wartend: number): string {
  const wir = `Wir rechnen mit ${anzahl} ${anzahl === 1 ? "Annahme" : "Annahmen"}.`;
  if (wartend === 0) return wir;
  return `${wir} ${wartend} ${wartend === 1 ? "wartet" : "warten"} auf die Fachabteilung.`;
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
      }[]
    >(SQL_ANNAHMEN);
    return zeilen.map((z) => ({
      nr: z.nr,
      rueckfrage: z.rueckfrage,
      wartet: z.wartet,
      regelName: z.regel_name,
      lieferungen: z.lieferungen,
      satz: alltag(z.satz),
    }));
  }, optionen);
}
