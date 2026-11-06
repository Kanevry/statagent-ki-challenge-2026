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
import {
  ABGABE,
  ANZAHL_LIEFERUNGEN,
  EINBRUCH,
  FREIGABE,
  GOLDEN_SET,
  LIEFERUNGEN,
  MASSSTAB_TEIL_VON_OESTERREICH,
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

const ERSTE = LIEFERUNGEN[0].lieferung;
const LETZTE = LIEFERUNGEN[LIEFERUNGEN.length - 1].lieferung;
const BRUCHWORT: Record<number, string> = { 10: "ein Zehntel" };

/**
 * Glossar-Erklärungen nach docs/sprache.md. Die Einträge Lieferung, Beleg, Revisionsbedarf, Qualitätsbericht
 * und Freigabe stehen wortgleich in shared/ui/src/bausteine/glossar.ts (Test: inhalt.test.ts).
 */
export const BEGRIFFE = {
  Lieferung: "Die Daten, die die Sozialversicherungsträger jeden Monat schicken.",
  Beschäftigungsverhältnis: "ein sozialversicherter Job; wer zwei Jobs hat, zählt zweimal",
  "Freier Dienstvertrag": "ein Job ohne Anstellung, trotzdem sozialversichert",
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
    { href: "#schritt-1", text: "Geschichte" },
    { href: "#datenfehler", text: "Auffälligkeiten" },
    { href: "#use-cases", text: "Use Cases" },
    { href: "#ansatz", text: "So arbeiten wir" },
    { href: "#team", text: "Team" },
  ],
  app: { href: "/uc3", text: "Zur App" },
  menue: "Menü",
  bereich: "Hauptnavigation",
} as const;

export const HERO = {
  titel: "StatAgent macht aus den Monatslieferungen der Sozialversicherung eine geprüfte Beschäftigten\u00adstatistik für den Dachverband.",
  satz: "Die KI schreibt den Code, gerechnet wird ohne KI, und ein Mensch gibt mit Namen frei.",
  knopf: "StatAgent öffnen",
  autor: "Von Bernhard Götzendorfer, Team OneShotAndy, KI Challenge 2026",
  hinweis: "Weiter nach unten: der Weg der Daten in fünf Schritten.",
} as const;

export interface GeschichteSchritt {
  titel: string;
  text: string;
  /** Erklärung eines Fachbegriffs unter dem Text */
  begriff?: { begriff: string; erklaerung: string };
}

const OKT = monatJahr(EINBRUCH.lieferung);
const fd = SZENE_BEFUNDE.fdFehlen2025_03;

/** Die fünf Schritte der Startseite. Jeder ist ohne Bewegung und ohne die Bühne vollständig lesbar. */
export const GESCHICHTE: readonly GeschichteSchritt[] = [
  {
    titel: `${zahl(ANZAHL_LIEFERUNGEN)} Lieferungen kommen an`,
    text: `Jeden Monat schicken die Sozialversicherungsträger ihre Daten, von ${monatJahr(ERSTE)} bis ${monatJahr(LETZTE)}. Das sind ${zahl(SUMME_ZEILEN)} Zeilen. Die Daten sind erfunden, in der Größe etwa ${BRUCHWORT[MASSSTAB_TEIL_VON_OESTERREICH]} Österreichs.`,
    begriff: begriff("Lieferung"),
  },
  {
    titel: "Das Programm prüft jede Zeile",
    text: `Feste Regeln laufen über alle Lieferungen und finden Auffälligkeiten, zum Beispiel ${zahl(SZENE_BEFUNDE.geburtsmonat13.saetze)} Geburtsdaten mit Monat 13 im ${monatJahr(SZENE_BEFUNDE.geburtsmonat13.lieferung)} oder ${zahl(fd.verhaeltnisse)} fehlende freie Dienstverträge im ${monatJahr(fd.lieferung)}. Die Oktober-Lieferung 2025 ist viel kleiner als sonst. Gelöscht wird nichts, jede Auffälligkeit wird vermerkt.`,
    begriff: begriff("Freier Dienstvertrag"),
  },
  {
    titel: `Im ${OKT} bricht die Zahl ein`,
    text: `In der Lieferung stehen ${zahl(EINBRUCH.geliefert)} Beschäftigungsverhältnisse, im Monat davor waren es ${zahl(EINBRUCH.vormonat)}. Im Monat danach sind fast alle wieder da, die Lieferung war also unvollständig. Das Programm hält den Monat an, statt den Einbruch zu veröffentlichen. ${zahl(EINBRUCH.uebernommen)} übernehmen wir aus der Lieferung davor, deshalb steht in der App ${zahl(EINBRUCH.vorlaeufig)}, vorläufig.`,
    begriff: begriff("Beschäftigungsverhältnis"),
  },
  {
    titel: "Ein Mensch gibt frei, mit Namen",
    text: `Das Programm veröffentlicht nichts allein. ${FREIGABE.name} hat ${zahl(FREIGABE.monate)} Monate mit Namen und Zeitpunkt freigegeben. ${MONATE[Number(FREIGABE.vorlaeufig[0].split("-")[1]) - 1]} und ${MONATE[Number(FREIGABE.vorlaeufig[1].split("-")[1]) - 1]} 2025 bleiben angehalten. Eine Freigabe mit „Team“ als Namen lehnt das System ab.`,
  },
  {
    titel: "Zahlen und Berichte stehen",
    text: `Zur Kontrolle rechnet StatAgent den Beispielbericht der Aufgabe für ${monatJahr(GOLDEN_SET.lieferung)} aus den Rohdaten nach: ${zahl(GOLDEN_SET.zellenExakt)} von ${zahl(GOLDEN_SET.zellenGesamt)} Zahlen stimmen genau. Dazu kommen ${zahl(ABGABE.qualitaetsberichte)} Qualitätsberichte und die Lieferung ans Ministerium für ${monatJahr(ABGABE.ministeriumMonat)} mit ${zahl(ABGABE.ministeriumPersonen)} Personen.`,
    begriff: begriff("Beleg"),
  },
];

/** Beschriftungen auf der Bühne. Alles steht auch im Text der Schritte, die Bühne ist für Screenreader ausgeblendet. */
export const BUEHNE = {
  erste: monatKurz(ERSTE),
  mitte: monatKurz(EINBRUCH.lieferung),
  letzte: monatKurz(LETZTE),
  erklaerung: "Jede Säule ist eine Monatslieferung.",
  ankunft: { wert: zahl(SUMME_ZEILEN), text: `Zeilen in ${zahl(ANZAHL_LIEFERUNGEN)} Lieferungen` },
  stand: (n: number) => `Schritt ${zahl(n)} von ${zahl(GESCHICHTE.length)}`,
  marken: [
    { wert: zahl(SZENE_BEFUNDE.geburtsmonat13.saetze), text: "mit Geburtsmonat 13" },
    { wert: zahl(fd.verhaeltnisse), text: "freie Dienstverträge fehlen" },
    { wert: zahl(EINBRUCH.zeilen), text: `Zeilen statt ${zahl(EINBRUCH.zeilenVormonat)}` },
  ],
  vormonat: { wert: zahl(EINBRUCH.vormonat), text: monatJahr("2025-09") },
  einbruch: { wert: zahl(EINBRUCH.geliefert), text: OKT, folge: `−${EINBRUCH.prozent} %, angehalten` },
  freigabe: {
    feld: "Freigegeben von",
    falsch: "Team",
    abgelehnt: "abgelehnt: Vor- und Nachname nötig",
    name: FREIGABE.name,
    zeit: `freigegeben am ${FREIGABE.zeit}`,
    gruen: `${zahl(FREIGABE.monate)} Monate veröffentlicht`,
    gelb: `${zahl(FREIGABE.vorlaeufig.length)} angehalten`,
  },
  raster: `Jedes Kästchen ist eine Zahl im Beispielbericht, alle ${zahl(GOLDEN_SET.zellenGesamt)} stimmen.`,
  ergebnis: [
    { wert: `${zahl(GOLDEN_SET.zellenExakt)} von ${zahl(GOLDEN_SET.zellenGesamt)}`, text: "Zahlen stimmen genau" },
    { wert: zahl(ABGABE.qualitaetsberichte), text: "Qualitätsberichte" },
    { wert: zahl(ABGABE.ministeriumPersonen), text: `Personen fürs Ministerium, ${monatKurz(ABGABE.ministeriumMonat)}` },
  ],
} as const;

/** Beleg im letzten Schritt: die echte Abfrage hinter einer Zahl. */
export const BELEG = {
  sql: GOLDEN_SET.belegSql,
  unterschrift: `Diese Abfrage ergibt ${zahl(GOLDEN_SET.bestand)}, genau so, wie sie hier steht.`,
} as const;

export const ANSATZ = {
  titel: "So arbeiten wir",
  einleitung: "Fünf Regeln, an die sich das ganze Projekt hält. Sie machen jede Zahl nachprüfbar.",
  punkte: [
    {
      bild: "rechnen",
      titel: "Die KI schreibt, das Programm rechnet",
      text: "Eigene Agenten schreiben Code und Regeln. Die Zahlen rechnet dieser Code ohne Sprachmodell, zwei Läufe ergeben dieselben Zahlen.",
    },
    {
      bild: "regeln",
      titel: "Regeln sind Daten",
      text: "Jede Regel steht mit Gültigkeit und Begründung in der Datenbank, die alte bleibt nachlesbar.",
    },
    {
      bild: "freigabe",
      titel: "Ein Mensch gibt frei",
      text: "Jede Änderung und jede Lieferung trägt Vor- und Nachnamen und Zeitpunkt.",
    },
    {
      bild: "beleg",
      titel: "Jede Zahl hat einen Beleg",
      text: "Zu jeder Zahl im Bericht gehört die Abfrage, die sie erzeugt hat.",
    },
    {
      bild: "lokal",
      titel: "Keine Einzeldaten ans Modell",
      text: "Das Sprachmodell sieht nur Regeln und den Aufbau der Tabellen, nie einzelne Zeilen.",
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
    `Gezeigt werden ${zahl(gezeigt)} von ${zahl(gesamt)} Auffälligkeiten: was einen Monat anhält zuerst, dann nicht erklärbare, dann die größten.`,
  /** Aufklapper unter den ersten Zeilen (UI-Regie): weitere Auffälligkeiten, falls es welche gibt, und immer die Begriffe. */
  mehr: (weitere: number) => (weitere > 0 ? `${zahl(weitere)} weitere Auffälligkeiten und Begriffe` : "Begriffe"),
  /** Glossar zur Spalte Einstufung (Roast K9); die drei Stufen stammen aus der Qualitätsbericht-Vorlage der Aufgabe. */
  glossar: [
    { begriff: "erklärt, plausibel", erklaerung: "ungewohnt, aber echt: zählt mit und wird vermerkt" },
    { begriff: "erklärt, Datenproblem", erklaerung: "ein Fehler in den Daten mit bekannter Ursache; eine feste Regel behebt ihn" },
    { begriff: "nicht erklärbar", erklaerung: "geht als Rückfrage an die Fachabteilung; der Monat bleibt vorläufig" },
    begriff("Revisionsbedarf"),
  ],
  datenbank: "Live aus der Datenbank von StatAgent, Stand",
  /** Weg zur ganzen Liste; steht nur bei Daten aus der Datenbank, die Beispieldaten haben keine Berichte dahinter. */
  berichte: { text: "Alle Auffälligkeiten je Monat stehen in den Qualitätsberichten", href: "/uc3/berichte" },
} as const;

export const USE_CASES = {
  titel: "Drei Use\u00a0Cases, ein Kern",
  einleitung: "Drei Anwendungen teilen sich eine Plattform, dazu kommt ein gemeinsamer Einstieg. Die Jury bewertet StatAgent.",
  oeffnen: "Öffnen",
  eintraege: {
    uc3: {
      text: `${zahl(ANZAHL_LIEFERUNGEN)} Monatslieferungen prüfen, zählen und belegen: eine Beschäftigtenstatistik mit Qualitätsbericht je Monat und Ministeriums-Lieferung.`,
    },
    uc1: {
      text: "Von der Situation bis zum Antrag: Leistungen der Sozialversicherung erkennen, mit Quelle, Antrag vorbereiten.",
    },
    uc2: {
      text: "Sechs Gruppen des Gesundheitswesens verhandeln eine Frage, ihre Positionen und Änderungen bleiben sichtbar.",
    },
  } satisfies Record<UcId, { text: string }>,
  /** Gemeinsamer Einstieg (Epic #95): Name und Route aus der Registry. */
  uc4: {
    text: "StatAgent rechnet die Zahl, der Simulator wägt ab, der Lotse sagt, was es für Sie heißt.",
  },
} as const;

export const TEAM = {
  titel: "Team OneShotAndy",
  produkt: "StatAgent von Bernhard Götzendorfer",
  text: "Beitrag zur KI Challenge 2026 des Dachverbands der österreichischen Sozialversicherungsträger. Bewertet wird Use Case 3.",
} as const;

export const FUSSZEILE = {
  repo: { href: "https://github.com/KIChallenge/OneShotAndy", text: "github.com/KIChallenge/OneShotAndy" },
  hinweise: ["Synthetische Daten, keine echten Personen"],
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
