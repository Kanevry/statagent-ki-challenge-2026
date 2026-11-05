/**
 * Alle Texte der Landingpage an einer Stelle, damit die Review-Runde sie prüfen und ändern kann.
 *
 * Regeln: deutsch, ohne Du/Sie-Anrede, „wir“ für das Team. Keine Gedankenstriche, keine Fragezeichen in
 * Überschriften, keine Floskeln. Jede Zahl kommt aus web/landing/daten/fakten.ts und wird mit `zahl()`
 * formatiert; hier steht keine Ziffernfolge, die nicht von dort stammt.
 *
 * Wörter nach der Wortliste docs/sprache.md: Begriffe der Aufgabenstellung mit Erklärung, keine eigenen
 * Kurzformen („Verhältnisse“, „Zellen“, „Sätze“, „Befunde“). Glossar-Texte, die es auch im gemeinsamen
 * Glossar gibt (shared/ui/src/bausteine/glossar.ts), sind wortgleich; inhalt.test.ts prüft das.
 */
import type { UcId } from "@kic/ui/ucs";
import type { BefundId } from "../szene/motor/layout";
import type { SchrittId } from "../szene/vertrag";
import {
  ANZAHL_LIEFERUNGEN,
  BUNDESLAENDER_2024_08,
  GOLDEN_SET,
  LIEFERUNGEN,
  BEFUNDE,
  MASSSTAB_TEIL_VON_OESTERREICH,
  MONATE_JE_LIEFERUNG,
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

/** „2025-10“ → „Oktober 2025“ (geschütztes Leerzeichen: Monat und Jahr brechen nicht auseinander) */
export function monatJahr(jjjjMm: string): string {
  const [jahr, monat] = jjjjMm.split("-");
  return `${MONATE[Number(monat) - 1]}\u00a0${jahr}`;
}

/** „2024-08“ → „08/2024“ */
export function monatKurz(jjjjMm: string): string {
  const [jahr, monat] = jjjjMm.split("-");
  return `${monat}/${jahr}`;
}

/** Jede Monatsangabe „JJJJ-MM“ in einem Anzeigetext → „MM/JJJJ“ (Wortliste: „2025-10“ nur in Code und Abfragen). */
export function monateLesbar(text: string): string {
  return text.replace(/\b(\d{4})-(\d{2})\b/g, "$2/$1");
}

/** auf Zehntausender gerundet, für „rund …“ */
const rund = (n: number) => Math.round(n / 10_000) * 10_000;

/** „31.08.2024“ → „31. August 2024“ */
function datumLang(ttMmJjjj: string): string {
  const [tag, monat, jahr] = ttMmJjjj.split(".");
  return `${Number(tag)}.\u00a0${MONATE[Number(monat) - 1]}\u00a0${jahr}`;
}

const ERSTE = LIEFERUNGEN[0].lieferung;
const LETZTE = LIEFERUNGEN[LIEFERUNGEN.length - 1].lieferung;
const LAENDER = BUNDESLAENDER_2024_08.filter((b) => b.code !== 0);
const UNBEKANNT = BUNDESLAENDER_2024_08.find((b) => b.code === 0);
const ZAHLWORT: Record<number, string> = { 3: "drei", 4: "vier", 5: "fünf", 9: "neun" };
const ORDNUNGSZAHL: Record<number, string> = { 4: "vierte", 5: "fünfte", 10: "zehnte" };
const BRUCHWORT: Record<number, string> = { 10: "ein Zehntel" };
const ZEILEN_JE_LIEFERUNG = rund(SUMME_ZEILEN / ANZAHL_LIEFERUNGEN);

/**
 * Glossar-Erklärungen nach docs/sprache.md. Die Einträge Lieferung, Beleg, Revisionsbedarf, Qualitätsbericht
 * und Freigabe stehen wortgleich in shared/ui/src/bausteine/glossar.ts (Test: inhalt.test.ts).
 */
export const BEGRIFFE = {
  Lieferung: "Die Daten eines Monats, so wie sie von den Sozialversicherungsträgern kommen.",
  Beschäftigungsverhältnis: "ein sozialversicherter Job; wer zwei Jobs hat, zählt zweimal",
  "Freier Dienstvertrag": "ein Job ohne Anstellung, trotzdem sozialversichert",
  Stichtag: "der letzte Tag des Monats; gezählt wird jedes Beschäftigungsverhältnis, das an diesem Tag besteht",
  Beispielbericht: `der Monatsbericht ${monatJahr(GOLDEN_SET.lieferung)} aus der Aufgabe, ${zahl(GOLDEN_SET.tabellen)} Tabellen im Layout des Dachverbands`,
  Beleg: "Zeigt, woher eine Zahl kommt: aus welcher Lieferung und mit welcher Abfrage sie gerechnet wurde.",
  Revisionsbedarf:
    "Eine schon veröffentlichte Zahl wäre mit den neuen Daten anders. Sie bleibt stehen, der Unterschied kommt in den Qualitätsbericht.",
} as const;

const begriff = (b: keyof typeof BEGRIFFE) => ({ begriff: b, erklaerung: BEGRIFFE[b] });

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
    { href: "#datenfehler", text: "Auffälligkeiten" },
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
  satz: `StatAgent macht aus ${zahl(ANZAHL_LIEFERUNGEN)} Monatslieferungen der Sozialversicherung eine geprüfte Beschäftigtenstatistik. Die KI schreibt Code und Regeln, gerechnet wird ohne KI, ein Mensch gibt mit Namen frei.`,
  /** Ergebnis auf einen Blick (Roast K3); Zahlen aus fakten.ts, Herkunft in `ergebnisQuelle`. */
  ergebnis: [
    { wert: zahl(ANZAHL_LIEFERUNGEN), text: "Monatslieferungen" },
    { wert: zahl(SUMME_ZEILEN), text: "Zeilen zusammen" },
    { wert: zahl(BEFUNDE.length), text: "Auffälligkeiten gefunden" },
    { wert: `${zahl(GOLDEN_SET.zellenExakt)} von ${zahl(GOLDEN_SET.zellenGesamt)}`, text: "Zahlen stimmen genau" },
  ],
  ergebnisBereich: "Ergebnis auf einen Blick",
  ergebnisQuelle: `Nachgerechnet am Beispielbericht der Aufgabe für ${monatJahr(GOLDEN_SET.lieferung)}, Stand 5. November 2026. Gelöscht wird nichts.`,
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
  /** Glossar-Untertitel je Fachbegriff (PRD Vertrag D, Roast K9) */
  glossar: { begriff: string; erklaerung: string }[];
}

const tl = SZENE_BEFUNDE.teilLieferung2025_10;
const fd = SZENE_BEFUNDE.fdFehlen2025_03;
/** „fünfte“: jedes wievielte Beschäftigungsverhältnis im Oktober 2025 fehlt */
const TEIL_FEHLT = ORDNUNGSZAHL[Math.round(100 / tl.anteilProzent)];
/** Monat nach der Teil-Lieferung, in dem fast alle wieder da sind (SZENE_BEFUNDE.wiederIn2025_11) */
const FOLGEMONAT = MONATE[Number(tl.lieferung.split("-")[1]) % 12];

export const SCHRITT_TEXTE: Record<SchrittId, SchrittText> = {
  lieferungen: {
    marke: "Einlesen",
    titel: "Jeden Monat kommen neue Daten",
    kennzahl: SUMME_ZEILEN,
    einheit: `Zeilen in ${zahl(ANZAHL_LIEFERUNGEN)} Monatslieferungen zusammen`,
    text: `Jede Säule ist ein Monat, von ${monatJahr(ERSTE)} bis ${monatJahr(LETZTE)}, mit rund ${zahl(ZEILEN_JE_LIEFERUNG)} Zeilen. Jede Lieferung enthält alle Beschäftigungsverhältnisse der letzten ${ZAHLWORT[MONATE_JE_LIEFERUNG]} Monate, viele stehen deshalb in mehreren Lieferungen. Die Daten sind erfunden, in der Größe etwa ${BRUCHWORT[MASSSTAB_TEIL_VON_OESTERREICH]} Österreichs.`,
    glossar: [begriff("Lieferung"), begriff("Beschäftigungsverhältnis")],
  },
  pruefen: {
    marke: "Prüfen",
    titel: "Die Prüfung findet, was nicht stimmt",
    kennzahl: tl.fehlen,
    einheit: `Beschäftigungsverhältnisse fehlen im ${monatJahr(tl.lieferung)}`,
    text: `Das ist jedes ${TEIL_FEHLT}, im ${FOLGEMONAT} sind fast alle wieder da: Die Lieferung war unvollständig. Ohne Prüfung hätte die Statistik einen Einbruch gezeigt, den es so nicht gab. Im ${monatJahr(fd.lieferung)} fehlen alle ${zahl(fd.verhaeltnisse)} freien Dienstverträge.`,
    glossar: [begriff("Freier Dienstvertrag")],
  },
  zaehlen: {
    marke: "Zählen",
    titel: "Gezählt wird nach festen Regeln",
    kennzahl: GOLDEN_SET.bestand,
    einheit: `Beschäftigungsverhältnisse am ${datumLang(GOLDEN_SET.stichtag)}`,
    text: `Gezählt wird am Stichtag, verteilt auf ${ZAHLWORT[LAENDER.length]} Bundesländer. ${zahl(UNBEKANNT?.anzahl ?? 0)} haben kein Bundesland: Sie zählen trotzdem mit und bleiben als eigene Gruppe sichtbar.`,
    glossar: [begriff("Stichtag")],
  },
  belegen: {
    marke: "Belegen",
    titel: "Jede Zahl hat einen Beleg",
    kennzahl: GOLDEN_SET.zellenExakt,
    einheit: `von ${zahl(GOLDEN_SET.zellenGesamt)} Zahlen stimmen genau`,
    text: `Die Aufgabe liefert einen Beispielbericht mit ${zahl(GOLDEN_SET.tabellen)} Tabellen. StatAgent rechnet ihn aus den Rohdaten nach, keine Zahl weicht ab. Zu jeder Zahl gehört die Abfrage, die sie erzeugt.`,
    glossar: [begriff("Beispielbericht"), begriff("Beleg")],
  },
};

export const BELEG = {
  sql: GOLDEN_SET.belegSql,
  unterschrift: `Diese Abfrage ergibt ${zahl(GOLDEN_SET.bestand)}, genau so, wie sie hier steht.`,
  tabelle: `Beschäftigungsverhältnisse am ${GOLDEN_SET.stichtag} nach Bundesland`,
  spalteLand: "Bundesland",
  spalteAnzahl: "Anzahl",
  summe: "Österreich",
} as const;

/** Beschriftungen an der Szene. Zahlen kommen aus dem Layout, das sie aus daten/fakten.ts übernimmt. */
export const SZENE_TEXTE = {
  befund: {
    "geburtsmonat-13": "mit Geburtsmonat 13",
    "bl-oenace-leer": "ohne Bundesland",
    volldubletten: "Zeilen doppelt",
    "fd-fehlen": "freie Dienstverträge fehlen",
    "teil-lieferung": "Beschäftigungsverhältnisse fehlen",
  } satisfies Record<BefundId, string>,
  /** mobil steht die Beschriftung einzeilig in 390 px; der Schritt-Text darunter nennt die Einheit */
  befundMobil: { "teil-lieferung": `fehlen, jedes ${TEIL_FEHLT}` } as Partial<Record<BefundId, string>>,
  unbekannt: "ohne Bundesland",
  legende: (n: number) => `1 Punkt steht für rund ${zahl(n)} Beschäftigungsverhältnisse`,
} as const;

export const ANSATZ = {
  titel: "So arbeiten wir",
  einleitung: `${ZAHLWORT[5].replace(/^./, (c) => c.toUpperCase())} Regeln, an die sich das ganze Projekt hält. Sie machen jede Zahl nachprüfbar.`,
  punkte: [
    {
      titel: "Agenten schreiben Code, das Programm rechnet",
      text: "Eigene Agenten setzen Änderungsaufträge um: Sie schreiben Code und Regeln. Die Zahlen rechnet dieser Code allein, ohne Sprachmodell. Zwei Läufe mit denselben Daten und Regeln liefern dieselben Zahlen.",
    },
    {
      titel: "Regeln sind Daten",
      text: "Wie eingelesen, geprüft und gezählt wird, steht als Regel in der Datenbank, mit Gültigkeit, Begründung und Freigabe. Ändert sich eine Regel, bleibt die alte nachlesbar. Nichts davon ist im Code versteckt.",
    },
    {
      titel: "Ein Mensch gibt frei, mit Namen",
      text: "Ein Agent schlägt jede Änderung vor, ein Mensch gibt sie mit Vor- und Nachnamen frei, das Protokoll hält Auftrag, Vorschlag und Freigabe fest. Auch jede Lieferung wird so freigegeben. Eine Freigabe mit „Team“ als Namen lehnt das System ab.",
      beispiel: "Freigegeben-von: Bernhard Götzendorfer",
    },
    {
      titel: "Jede Zahl hat einen Beleg",
      text: "Zu jedem Wert im Bericht gehört die Abfrage, die ihn erzeugt hat. Wer nachrechnen will, kann das Zeile für Zeile.",
    },
    {
      titel: "Statistikdaten bleiben lokal",
      text: "Die Statistikdaten von StatAgent liegen in einer Datenbank auf dem eigenen Rechner und verlassen ihn nicht. Das Sprachmodell sieht nur Regeln und den Aufbau der Tabellen, nie einzelne Zeilen.",
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
  titel: "Auffälligkeiten in den Lieferungen, nichts davon gelöscht",
  unterzeile: `Nachgerechnet am Beispielbericht für ${monatJahr(GOLDEN_SET.lieferung)}: ${zahl(GOLDEN_SET.zellenExakt)} von ${zahl(GOLDEN_SET.zellenGesamt)} Zahlen stimmen genau.`,
  einleitung:
    "Die Prüfung markiert jede Auffälligkeit und stuft sie ein. Was sich nicht erklären lässt, geht als Rückfrage an die Fachabteilung. Schon veröffentlichte Monate ändern wir nicht; bringt eine spätere Lieferung andere Daten, steht das als Revisionsbedarf im Qualitätsbericht.",
  beschriftung: "Auffälligkeiten der Prüfung mit Lieferung, Anzahl und Einstufung",
  spalten: { befund: "Auffälligkeit", lieferung: "Lieferung", saetze: "Anzahl", einstufung: "Einstufung" },
  rueckfrage: "Rückfrage",
  beispieldaten:
    "Beispiel vom 5. November 2026, nicht live. In der App entsteht diese Liste bei jeder Lieferung neu aus der Prüfung.",
  keineTreffer:
    "Beispiel vom 5. November 2026, nicht live: In dieser Datenbank ist noch keine Lieferung geprüft.",
  /** Hinweis, wenn die Datenbank mehr Treffer hat, als die Tabelle zeigt */
  auswahl: (gezeigt: number, gesamt: number) =>
    `Gezeigt werden ${zahl(gezeigt)} von ${zahl(gesamt)} Auffälligkeiten, nicht erklärbare zuerst, dann die größten.`,
  /** Glossar zur Spalte Einstufung (Roast K9); die drei Stufen stammen aus der Qualitätsbericht-Vorlage der Aufgabe. */
  glossar: [
    { begriff: "erklärt, plausibel", erklaerung: "ungewohnt, aber echt: zählt mit und wird vermerkt" },
    { begriff: "erklärt, Datenproblem", erklaerung: "ein Fehler in den Daten mit bekannter Ursache; eine feste Regel behebt ihn" },
    { begriff: "nicht erklärbar", erklaerung: "geht als Rückfrage an die Fachabteilung; der Monat bleibt vorläufig" },
    begriff("Revisionsbedarf"),
  ],
  datenbank: "Live aus der Datenbank von StatAgent, Stand",
} as const;

export const USE_CASES = {
  titel: "Drei Use\u00a0Cases, ein Kern",
  einleitung: "Drei Anwendungen teilen sich eine Plattform. Die Jury bewertet StatAgent. Ein vierter Eintrag ist noch verdeckt.",
  oeffnen: "Öffnen",
  bewertet: "bewertet",
  eintraege: {
    uc3: {
      text: `${zahl(ANZAHL_LIEFERUNGEN)} Monatslieferungen prüfen, zählen und belegen: eine Beschäftigtenstatistik mit Qualitätsbericht je Monat und Ministeriums-Lieferung.`,
      schritte: ["Einlesen", "Prüfen", "Zählen", "Freigeben", "Bereitstellen"],
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
    beispiel: "„Wie entwickelt sich die Beschäftigung im Gesundheits- und Sozialwesen in meinem Bundesland, und was heißt das für mich?“",
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
