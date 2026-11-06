/**
 * Fakten der Landingpage: jede Zahl mit Beleg. Einzige Quelle für Szene, Texte und Tabelle.
 *
 * Herkunft:
 * - Zeilen je Lieferung: `select lieferung, count(*) from roh.lieferung group by 1`, lokal PG 5433,
 *   gemessen 05.11.2026 (Summe 10.152.292, deckt sich mit PRD E0/E1 Pre-Mortem).
 * - Bundesländer 08/2024 und alle Befunde: Gegenrechnung Beispielbericht gegen Rohdaten
 *   (Golden Set 08/2024, Gegenrechnung des Teams vom 05.11.2026), Abschnitte 1, 3, 7, 8, 9.
 * Nichts hier wird zur Laufzeit gerechnet; die Zahlen rechnet die Datenbank, nicht die Seite.
 */

export interface Lieferung {
  /** JJJJ-MM */
  lieferung: string;
  /** Zeilen in roh.lieferung */
  zeilen: number;
}

export const LIEFERUNGEN: readonly Lieferung[] = [
  { lieferung: "2024-08", zeilen: 392_284 },
  { lieferung: "2024-09", zeilen: 407_526 },
  { lieferung: "2024-10", zeilen: 420_576 },
  { lieferung: "2024-11", zeilen: 426_559 },
  { lieferung: "2024-12", zeilen: 426_546 },
  { lieferung: "2025-01", zeilen: 424_363 },
  { lieferung: "2025-02", zeilen: 424_641 },
  { lieferung: "2025-03", zeilen: 425_151 },
  { lieferung: "2025-04", zeilen: 425_831 },
  { lieferung: "2025-05", zeilen: 428_948 },
  { lieferung: "2025-06", zeilen: 432_086 },
  { lieferung: "2025-07", zeilen: 435_070 },
  { lieferung: "2025-08", zeilen: 433_286 },
  { lieferung: "2025-09", zeilen: 434_104 },
  { lieferung: "2025-10", zeilen: 345_078 },
  { lieferung: "2025-11", zeilen: 428_277 },
  { lieferung: "2025-12", zeilen: 427_870 },
  { lieferung: "2026-01", zeilen: 425_360 },
  { lieferung: "2026-02", zeilen: 426_706 },
  { lieferung: "2026-03", zeilen: 428_560 },
  { lieferung: "2026-04", zeilen: 428_910 },
  { lieferung: "2026-05", zeilen: 431_862 },
  { lieferung: "2026-06", zeilen: 434_517 },
  { lieferung: "2026-07", zeilen: 438_181 },
] as const;

export const SUMME_ZEILEN = 10_152_292;
export const ANZAHL_LIEFERUNGEN = 24;

/**
 * Aus der Fachbeschreibung der Aufgabe (svbox/uc3/Fachbeschreibung.md, Abschnitte 1 und 2):
 * Jede Lieferung ist ein Vollabzug mit allen Beschäftigungsverhältnissen der letzten drei Monate;
 * die Größenordnung der synthetischen Daten ist etwa ein Zehntel Österreichs.
 */
export const MONATE_JE_LIEFERUNG = 3;
export const MASSSTAB_TEIL_VON_OESTERREICH = 10;

/** Bundesland-Codes wie klassifikation bundesland.csv (0 = unbekannt). */
export type BundeslandCode = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9;

export interface Bundesland {
  code: BundeslandCode;
  name: string;
  /** Kürzel für enge Beschriftung (mobil) */
  kurz: string;
  /** Verhältnisse am Stichtag 31.08.2024 laut Beispielbericht Tab2, nachgerechnet 132/132 Zellen */
  anzahl: number;
}

export const BUNDESLAENDER_2024_08: readonly Bundesland[] = [
  { code: 1, name: "Burgenland", kurz: "B", anzahl: 11_265 },
  { code: 2, name: "Kärnten", kurz: "K", anzahl: 22_385 },
  { code: 3, name: "Niederösterreich", kurz: "NÖ", anzahl: 64_505 },
  { code: 4, name: "Oberösterreich", kurz: "OÖ", anzahl: 68_141 },
  { code: 5, name: "Salzburg", kurz: "S", anzahl: 26_968 },
  { code: 6, name: "Steiermark", kurz: "St", anzahl: 53_901 },
  { code: 7, name: "Tirol", kurz: "T", anzahl: 35_437 },
  { code: 8, name: "Vorarlberg", kurz: "V", anzahl: 16_839 },
  { code: 9, name: "Wien", kurz: "W", anzahl: 90_799 },
  { code: 0, name: "Bundesland unbekannt", kurz: "?", anzahl: 1_996 },
] as const;

/** Golden Set 08/2024 */
export const GOLDEN_SET = {
  stichtag: "31.08.2024",
  lieferung: "2024-08",
  zeilenInLieferung: 392_284,
  endeVorStichtag: 48,
  bestand: 392_236,
  maenner: 211_603,
  frauen: 180_633,
  zellenExakt: 2_880,
  zellenGesamt: 2_880,
  tabellen: 13,
  /** Vollständige Abfrage; ergibt lokal (PG 5433, 05.11.2026) genau `bestand` = 392.236. */
  belegSql:
    "select count(distinct vvh_id) from roh.lieferung\n" +
    " where lieferung = '2024-08'\n" +
    "   and beginn <= '2024-08-31'\n" +
    "   and (ende is null or ende >= '2024-08-31');",
} as const;

export type Einstufung = "erklaert-plausibel" | "erklaert-datenproblem" | "nicht-erklaerbar" | "revision";

export interface Befund {
  id: string;
  befund: string;
  lieferung: string;
  /** Anzeige, deutsche Tausenderpunkte */
  saetze: string;
  einstufung: Einstufung;
  /** Anzeige der Einstufung */
  einstufungText: string;
  /** Rückfrage an die Fachabteilung, falls gestellt */
  rueckfrage?: string;
  /** Kurzer Beleg: Abfrage oder Abschnitt der Gegenrechnung */
  beleg: string;
}

/**
 * Die 8 Arten von Auffälligkeiten der Gegenrechnung (Pen-Frame c0eRD, Tabelle der Landing).
 * Einstufung wie in den Qualitätsberichten abgabe/qualitaetsberichte/*.md, Rückfragen wie abgabe/rueckfragen/R*.md.
 */
export const BEFUNDE: readonly Befund[] = [
  {
    id: "geburtsmonat-13",
    befund: "Geburtsmonat 13",
    lieferung: "ab 2024-08",
    saetze: "370",
    einstufung: "erklaert-datenproblem",
    einstufungText: "Fehler in den Daten",
    rueckfrage: "R1",
    beleg: "substr(geburtsdatum, 6, 2) = '13'",
  },
  {
    id: "alter-117-153",
    befund: "Alter 117 bis 153 Jahre",
    lieferung: "2024-08",
    saetze: "7",
    einstufung: "erklaert-datenproblem",
    einstufungText: "Fehler in den Daten",
    rueckfrage: "R6",
    beleg: "geburtsdatum < '1949-09-01'",
  },
  {
    id: "oenace-2003",
    befund: "Alte Branchencodes (ÖNACE 2003, DA bis DN)",
    lieferung: "alle 24",
    // gemessen 05.11.2026 je Lieferung: 40 (2025-10) bis 51 (2025-09) Zeilen, meist 49 oder 50
    saetze: "40 bis 51 je Lieferung",
    einstufung: "erklaert-datenproblem",
    einstufungText: "Fehler in den Daten",
    beleg: "oenace ~ '^D[A-N]$' → C",
  },
  {
    id: "bl-oenace-leer",
    befund: "Bundesland und Branche fehlen, immer gemeinsam",
    lieferung: "2024-08",
    saetze: "1.996",
    einstufung: "erklaert-datenproblem",
    einstufungText: "Fehler in den Daten",
    beleg: "bundesland is null and oenace is null",
  },
  {
    id: "volldubletten",
    befund: "Doppelte Zeilen, alle Felder gleich",
    lieferung: "2025-03",
    saetze: "1.663 Zeilen, 1.523 doppelt am Stichtag",
    einstufung: "erklaert-datenproblem",
    einstufungText: "Fehler in den Daten",
    rueckfrage: "R7",
    beleg: "group by alle Felder having count(*) > 1",
  },
  {
    id: "fd-fehlen",
    befund: "Freie Dienstverträge fehlen ganz",
    lieferung: "2025-03",
    saetze: "1.492",
    einstufung: "erklaert-datenproblem",
    einstufungText: "Fehler in den Daten",
    rueckfrage: "R4",
    beleg: "count(*) filter (where qual like '%FD') = 0",
  },
  {
    id: "teil-lieferung",
    befund: "Teil-Lieferung, rund 20 % fehlen",
    lieferung: "2025-10",
    saetze: "78.949, davon 78.733 in 2025-11 wieder da",
    einstufung: "erklaert-datenproblem",
    einstufungText: "Fehler in den Daten",
    rueckfrage: "R3",
    beleg: "offen in 2025-09, fehlt in 2025-10",
  },
  {
    id: "revision-dezember",
    befund: "Revisionsbedarf Dezember",
    lieferung: "2024-12 → 2025-01",
    saetze: "−260 (−0,067 %)",
    einstufung: "revision",
    einstufungText: "Revisionsbedarf ausgewiesen",
    beleg: "387.390 → 387.130",
  },
] as const;

/** Kennzahlen für die Szene (Schritt „Prüfen“). */
export const SZENE_BEFUNDE = {
  dubletten2025_03: { lieferung: "2025-03", zeilen: 1_663, doppeltAmStichtag: 1_523 },
  fdFehlen2025_03: { lieferung: "2025-03", verhaeltnisse: 1_492, vorher: "2025-02", nachher: "2025-04" },
  teilLieferung2025_10: {
    lieferung: "2025-10",
    fehlen: 78_949,
    wiederIn2025_11: 78_733,
    anteilProzent: 20,
    bestandVormonat: 394_200,
  },
  geburtsmonat13: { lieferung: "2024-08", saetze: 370 },
  blOenaceLeer: { lieferung: "2024-08", saetze: 1_996 },
  revisionDezember: { alt: 387_390, neu: 387_130, differenz: -260 },
} as const;

/** Deutsche Zahlformatierung mit Tausenderpunkt, ohne Locale-Abhängigkeit der Laufzeit. */
export function zahl(n: number): string {
  const vorzeichen = n < 0 ? "−" : "";
  const s = Math.abs(Math.round(n)).toString();
  return vorzeichen + s.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}
