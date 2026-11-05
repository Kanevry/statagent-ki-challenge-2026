/**
 * Alle Texte der Landingpage an einer Stelle, damit die Review-Runde sie prüfen und ändern kann.
 *
 * Regeln: deutsch, ohne Du/Sie-Anrede, „wir“ für das Team. Keine Gedankenstriche, keine Fragezeichen in
 * Überschriften, keine Floskeln. Jede Zahl kommt aus web/landing/daten/fakten.ts und wird mit `zahl()`
 * formatiert; hier steht keine Ziffernfolge, die nicht von dort stammt.
 */
import type { UcId } from "@kic/ui/ucs";
import type { SchrittId } from "../szene/vertrag";
import {
  ANZAHL_LIEFERUNGEN,
  BUNDESLAENDER_2024_08,
  GOLDEN_SET,
  LIEFERUNGEN,
  SUMME_ZEILEN,
  SZENE_BEFUNDE,
  zahl,
} from "../daten/fakten";

const MONATE = [
  "Jänner",
  "Februar",
  "März",
  "April",
  "Mai",
  "Juni",
  "Juli",
  "August",
  "September",
  "Oktober",
  "November",
  "Dezember",
] as const;

/** „2025-10“ → „Oktober 2025“ */
export function monatJahr(jjjjMm: string): string {
  const [jahr, monat] = jjjjMm.split("-");
  return `${MONATE[Number(monat) - 1]} ${jahr}`;
}

/** „2024-08“ → „08/2024“ */
function monatKurz(jjjjMm: string): string {
  const [jahr, monat] = jjjjMm.split("-");
  return `${monat}/${jahr}`;
}

/** „31.08.2024“ → „31. August 2024“ */
function datumLang(ttMmJjjj: string): string {
  const [tag, monat, jahr] = ttMmJjjj.split(".");
  return `${Number(tag)}. ${MONATE[Number(monat) - 1]} ${jahr}`;
}

const ERSTE = LIEFERUNGEN[0].lieferung;
const LETZTE = LIEFERUNGEN[LIEFERUNGEN.length - 1].lieferung;
const LAENDER = BUNDESLAENDER_2024_08.filter((b) => b.code !== 0);
const UNBEKANNT = BUNDESLAENDER_2024_08.find((b) => b.code === 0);
const ZAHLWORT: Record<number, string> = { 4: "vier", 5: "fünf", 9: "neun" };
const ORDNUNGSZAHL: Record<number, string> = { 4: "vierte", 5: "fünfte", 10: "zehnte" };

export const SEITE = {
  titel: "StatAgent · Team OneShotAndy · KI Challenge 2026",
  beschreibung:
    `StatAgent prüft, zählt und belegt eine Beschäftigtenstatistik aus ${zahl(ANZAHL_LIEFERUNGEN)} Monatslieferungen: Die KI schreibt den Code, das Programm rechnet, ein Mensch gibt frei.`,
  sprungZumInhalt: "Zum Inhalt springen",
} as const;

export const NAVIGATION = {
  wortmarke: "StatAgent",
  team: "OneShotAndy",
  startseite: "StatAgent, zum Seitenanfang",
  marken: [
    { href: "#ansatz", text: "Ansatz" },
    { href: "#datenfehler", text: "Datenfehler" },
    { href: "#use-cases", text: "Use Cases" },
    { href: "#team", text: "Team" },
  ],
  app: { href: "/uc3", text: "Zur App" },
  menue: "Menü",
  bereich: "Hauptnavigation",
} as const;

export const HERO = {
  titel: "StatAgent",
  autor: "by Bernhard Götzendorfer",
  leitmotiv: ["Hochrisikodaten", "Vertrauen", "Glaubwürdigkeit"] as const,
  satz: `Eine Beschäftigtenstatistik aus ${zahl(ANZAHL_LIEFERUNGEN)} Monatslieferungen. Die KI schreibt den Code, das Programm rechnet, ein Mensch gibt jede Zahl frei.`,
  hinweis: `Weiter nach unten: in ${ZAHLWORT[4]} Schritten von den Rohdaten zur belegten Zahl.`,
  schritteBereich: "Die vier Schritte",
  springeZu: "Springe zu Schritt",
} as const;

export interface SchrittText {
  /** kurzer Name in der Fortschrittsleiste */
  marke: string;
  titel: string;
  kennzahl: number;
  /** Zeile unter der Kennzahl */
  einheit: string;
  text: string;
}

const tl = SZENE_BEFUNDE.teilLieferung2025_10;
const fd = SZENE_BEFUNDE.fdFehlen2025_03;
const dub = SZENE_BEFUNDE.dubletten2025_03;

export const SCHRITT_TEXTE: Record<SchrittId, SchrittText> = {
  lieferungen: {
    marke: "Lieferungen",
    titel: "Jeden Monat kommt eine Lieferung",
    kennzahl: SUMME_ZEILEN,
    einheit: `Zeilen in ${zahl(ANZAHL_LIEFERUNGEN)} Lieferungen`,
    text: `${monatJahr(ERSTE)} bis ${monatJahr(LETZTE)}. Jede Säule ist eine Lieferung. Die Daten sind synthetisch, aber so groß und so fehlerhaft wie echte.`,
  },
  pruefen: {
    marke: "Prüfen",
    titel: "Die Prüfung findet, was nicht stimmt",
    kennzahl: tl.fehlen,
    einheit: `Verhältnisse fehlen im ${monatJahr(tl.lieferung)}`,
    text: `Das ist rund jedes ${ORDNUNGSZAHL[Math.round(100 / tl.anteilProzent)]}. Im ${monatJahr(fd.lieferung)} fehlen alle ${zahl(fd.verhaeltnisse)} freien Dienstverträge, dazu kommen ${zahl(dub.zeilen)} doppelte Zeilen. Wir löschen nichts: Jeder Befund wird markiert, eingestuft und als Rückfrage gestellt.`,
  },
  zaehlen: {
    marke: "Zählen",
    titel: "Gezählt wird nach festen Regeln",
    kennzahl: GOLDEN_SET.bestand,
    einheit: `Beschäftigungsverhältnisse am ${datumLang(GOLDEN_SET.stichtag)}`,
    text: `Verteilt auf ${ZAHLWORT[LAENDER.length]} Bundesländer. ${zahl(UNBEKANNT?.anzahl ?? 0)} ohne Bundesland zählen mit und bleiben sichtbar.`,
  },
  belegen: {
    marke: "Belegen",
    titel: "Jede Zahl hat einen Beleg",
    kennzahl: GOLDEN_SET.zellenExakt,
    einheit: `von ${zahl(GOLDEN_SET.zellenGesamt)} Zellen exakt`,
    text: "So viele Zellen stimmen mit dem Beispielbericht überein. Zu jeder Zahl gehört die Abfrage, die sie erzeugt.",
  },
};

export const BELEG = {
  sql: GOLDEN_SET.belegSql,
  unterschrift: `Die Abfrage hinter ${zahl(GOLDEN_SET.bestand)}`,
  tabelle: `Beschäftigungsverhältnisse am ${GOLDEN_SET.stichtag} nach Bundesland`,
  spalteLand: "Bundesland",
  spalteAnzahl: "Anzahl",
  summe: "Österreich",
} as const;

export const ANSATZ = {
  titel: "So arbeiten wir",
  einleitung: `${ZAHLWORT[5].replace(/^./, (c) => c.toUpperCase())} Regeln, an die sich das ganze Projekt hält. Sie machen jede Zahl nachprüfbar.`,
  punkte: [
    {
      titel: "Die KI schreibt Code, das Programm rechnet",
      text: "Ein Sprachmodell hilft uns beim Schreiben des Codes. Die Zahlen rechnet dieser Code allein, ohne Sprachmodell. Zwei Läufe mit denselben Daten und Regeln liefern dieselben Zahlen.",
    },
    {
      titel: "Regeln sind Daten",
      text: "Wie eingelesen, geprüft und gezählt wird, steht versioniert in der Datenbank, mit Gültigkeit, Begründung und Freigabe. Keine Zuordnung ist im Code versteckt.",
    },
    {
      titel: "Ein Mensch gibt frei, mit Namen",
      text: "Jede Regeländerung und jede Lieferung trägt Vor- und Nachnamen und Zeitpunkt. Eine Freigabe mit „Team“ als Namen lehnt das System ab.",
      beispiel: "Freigegeben-von: Bernhard Götzendorfer",
    },
    {
      titel: "Jede Zahl hat einen Beleg",
      text: "Zu jedem Wert im Bericht gehört die Abfrage, die ihn erzeugt hat. Wer nachrechnen will, kann das Zeile für Zeile.",
    },
    {
      titel: "Lokal und offline",
      text: "Die Daten liegen in PostgreSQL auf dem eigenen Rechner. Das Sprachmodell sieht Regeln und Schemata, nie Einzeldaten.",
    },
  ],
  modell: {
    text: "Sprachmodell austauschbar:",
    anbieter: [
      { name: "azure", zusatz: "Standard für UC3" },
      { name: "mistral" },
      { name: "ollama" },
      { name: "mock" },
    ],
  },
} as const;

export const DATENFEHLER = {
  titel: "Gefundene Datenfehler, nichts davon gelöscht",
  unterzeile: `Gegengerechnet am Beispielbericht ${monatKurz(GOLDEN_SET.lieferung)}: ${zahl(GOLDEN_SET.zellenExakt)} von ${zahl(GOLDEN_SET.zellenGesamt)} Zellen exakt.`,
  einleitung:
    "Die Prüfung markiert jeden Befund und stuft ihn ein. Was sich nicht erklären lässt, geht als Rückfrage an die Fachabteilung. Veröffentlichte Monate bleiben unverändert, Abweichungen stehen als Revisionsbedarf im Qualitätsbericht.",
  beschriftung: "Befunde der Prüfung mit Lieferung, Anzahl der Sätze und Einstufung",
  spalten: { befund: "Befund", lieferung: "Lieferung", saetze: "Sätze", einstufung: "Einstufung" },
  rueckfrage: "Rückfrage",
  beispieldaten: "Beispieldaten aus der Gegenrechnung vom 05.11.2026. Die UC3-Datenbank ist hier nicht verbunden.",
  datenbank: "Live aus der UC3-Datenbank, Stand",
} as const;

export const USE_CASES = {
  titel: "Drei Use\u00a0Cases, ein Kern",
  einleitung: "Drei Anwendungen teilen sich eine Plattform. Die Jury bewertet StatAgent. Ein vierter Eintrag ist noch verdeckt.",
  oeffnen: "Öffnen",
  bewertet: "bewertet",
  eintraege: {
    uc3: {
      text: `Lieferungen prüfen, Klassifikationen historisieren, ${zahl(ANZAHL_LIEFERUNGEN)} Monate Beschäftigtenstatistik mit Qualitätsbericht und Ministeriums-Lieferung.`,
      schritte: ["Einlesen", "Prüfen", "Zählen", "Freigeben", "Liefern"],
    },
    uc1: {
      text: "Von der Situation bis zum Antrag: Leistungen der Sozialversicherung erkennen, mit Quelle, Antrag vorbereiten.",
      schritte: ["Situation", "Leistung", "Quelle", "Antrag"],
    },
    uc2: {
      text: "Institutionelle Personas verhandeln eine gesundheitspolitische Frage, Positionen und ihre Änderungen bleiben sichtbar.",
      schritte: ["Frage", "Personas", "Positionen", "Änderungen"],
    },
  } satisfies Record<UcId, { text: string; schritte: string[] }>,
  /** Use Case 4 (Epic #95): verdeckt, deckt sich auf Klick auf. */
  uc4: {
    verdeckt: "Use Case 4",
    aufdecken: "Aufdecken",
    zudecken: "Wieder verdecken",
    name: "Gemeinsamer Einstieg",
    plakette: "neu",
    text: "Kein viertes Produkt, sondern die Verbindung der drei. Eine Frage läuft durch alle Räume: StatAgent liefert die geprüften Zahlen mit Beleg, das Panel verhandelt daraus eine Position, der KI-Lotse erklärt in einfacher Sprache, was das im Alltag bedeutet.",
    beispiel: "„Wie entwickeln sich die Wartezeiten, und was heißt das für mich?“",
    beispielLabel: "Beispielfrage",
    schritte: ["StatAgent: Zahlen mit Beleg", "Panel: Position", "KI-Lotse: einfache Sprache"],
    inArbeit: "Entsteht gerade",
    route: "/uc4",
  },
} as const;

export const TEAM = {
  titel: "Team OneShotAndy",
  produkt: "StatAgent by Bernhard Götzendorfer",
  text: "Beitrag zur KI Challenge 2026 des Dachverbands der österreichischen Sozialversicherungsträger. Bewertet wird Use Case 3.",
} as const;

export const FUSSZEILE = {
  repo: { href: "https://github.com/KIChallenge/OneShotAndy", text: "github.com/KIChallenge/OneShotAndy" },
  abgabe: "Abgabe Fr 06.11. 09:00",
  ablage: "SV-Box-Teamordner",
  hinweise: ["Synthetische Daten, keine echten Personen"],
  quelle: "Grenzen der Bundesländer: Statistik Austria, data.statistik.gv.at, bearbeitet von Flooh Perlot, CC BY 4.0",
} as const;

/**
 * Logos der Ausrichter in der Fußzeile (Owner 05.11. 14:0x: „dezent und angemessen sichtbar“, kein Logo im Hero).
 * Dateien unter web/public/landing/logos/; ein Eintrag erscheint erst, wenn er hier steht.
 * Breite/Höhe = natürliche Pixelmaße der Datei (verhindert Layout-Sprung).
 */
export const AUSRICHTER: {
  zeile: string;
  logos: { src: string; alt: string; href: string; breite: number; hoehe: number }[];
} = {
  zeile:
    "Eine Teilnahme an der KI Challenge 2026 des Dachverbands der Sozialversicherungsträger und der Wirtschaftskammer Wien",
  logos: [
    {
      src: "/landing/logos/dvsv-logo.png",
      alt: "Österreichische Sozialversicherung, Dachverband der Sozialversicherungsträger",
      href: "https://www.sozialversicherung.at/",
      breite: 576,
      hoehe: 206,
    },
    {
      src: "/landing/logos/wko-logo-hell.svg",
      alt: "Wirtschaftskammer Wien",
      href: "https://www.wko.at/wien",
      breite: 160,
      hoehe: 38,
    },
  ],
};
