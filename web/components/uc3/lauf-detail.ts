import { formatZahl } from "@kic/ui/bausteine";
import { literal } from "./beleg";
import { lies, type Lesung, type Sql } from "./db";
import { ladeMassgeblichenLauf } from "./laeufe";
import { monatName, monatsgrenzen, stichtag, verschieben } from "./monat";
import type { Lauf } from "./typen";

// Lauf-Detail /uc3/laeufe/[lieferung] (#18, Frames fFDc8 und P6gBQD): Leser, Sätze und Beleg-Abfragen eines Monats.
// Jede Abfrage, die ein Beleg ZEIGT, liefert genau die Zahl, die daneben steht; ausgeführt wird die parametrisierte
// Fassung mit denselben Bedingungen.

const GUELTIG = "('fertig', 'unveraendert')";

export type Einstufung = "erklaert-plausibel" | "erklaert-datenproblem" | "nicht-erklaerbar";

export interface Treffer {
  regelId: number;
  name: string;
  art: string;
  beschreibung: string;
  /** Satzvorlage aus meta.regel.parameter->>'satz' mit {anzahl}, {monat}, {umfang}; fehlt in älteren Ständen. */
  satz: string | null;
  ebene: string;
  anzahl: number;
  umfang: string | null;
  einstufung: Einstufung | null;
  massnahme: string | null;
  anhalten: boolean;
  belegSql: string | null;
  /** Offene Rückfragen (meta.rueckfrage ohne Antwort), auf die der Treffer verweist. */
  offeneRueckfragen?: string[];
}

export interface Ursache {
  ursache: string;
  anzahl: number;
}

export interface Revision {
  berichtsmonat: string;
  veroeffentlicht: number;
  aktuell: number;
  differenz: number;
  statusVorher: string;
  /** Summe gleich, aber Gruppen (Geschlecht, ÖNACE, Bundesland …) verschieben sich. */
  umgeschichtet: boolean;
  ursachen: Ursache[];
}

/** Revisionsbedarf wie im Qualitätsbericht: Summe anders oder Umschichtung zwischen Gruppen. */
export function hatRevisionsbedarf(r: Pick<Revision, "differenz" | "umgeschichtet">): boolean {
  return r.differenz !== 0 || r.umgeschichtet;
}

export interface Region {
  code: string;
  name: string;
  anzahl: number;
}

export interface Determinismus {
  laeufe: number;
  hashes: number;
  hash: string;
}

/** Was `uv run uc3 veroeffentlichen` vor dem Veröffentlichen prüft (statagent/lauf.py, veroeffentlichen). */
export interface VeroeffentlichenLage {
  /** Aktive, für die Lieferung gültige Regeln ohne Freigabe mit Namen. */
  regelnOhneFreigabe: number;
  /** Ist der Regelstand des Laufs für diese Lieferung freigegeben (meta.regelstand_freigabe)? */
  regelstandFreigegeben: boolean;
  /** Offene Rückfragen, auf die der Monat wartet (anhaltende Prüfungen, Fortschreibung E07). */
  wartetAuf: string[];
}

export interface LaufDetail {
  lauf: Lauf;
  veroeffentlichen: VeroeffentlichenLage;
  vormonat: Lauf | null;
  /** Gibt es für den Monat davor bzw. danach einen Lauf? Dann verlinkt die Seite dorthin. */
  davor: boolean;
  danach: boolean;
  treffer: Treffer[];
  revisionen: Revision[];
  regionen: Region[];
  determinismus: Determinismus;
}

function zahl(wert: unknown): number {
  const n = Number(wert ?? 0);
  return Number.isFinite(n) ? n : 0;
}

// ---------------------------------------------------------------------------------------------------------------
// Sätze

/** „1 Verhältnis“, „2 Verhältnisse“. */
export function verhaeltnisse(n: number): string {
  return `${formatZahl(n)} ${n === 1 ? "Verhältnis" : "Verhältnisse"}`;
}

export function aufzaehlen(teile: readonly string[]): string {
  return teile.length < 2 ? (teile[0] ?? "") : `${teile.slice(0, -1).join(", ")} und ${teile.at(-1)}`;
}

/**
 * Einstufung als Status: Art für Symbol und Farbe, Wort für den Text. Ohne Einstufung gilt ein Treffer wie im
 * Qualitätsbericht-Generator als nicht erklärbar.
 */
export function einstufungStatus(
  einstufung: Einstufung | null,
  offeneRueckfragen?: readonly string[],
): { art: "ok" | "warnung" | "fehler" | "info"; wort: string } {
  const e = einstufung ?? "nicht-erklaerbar";
  const wartet = wartetSatz(offeneRueckfragen);
  if (e === "nicht-erklaerbar" && wartet) return { art: "warnung", wort: `nicht erklärbar, ${wartet}` };
  switch (e) {
    case "erklaert-plausibel":
      return { art: "ok", wort: "erklärt, plausibel" };
    case "erklaert-datenproblem":
      return { art: "warnung", wort: "erklärt, Datenproblem" };
    default:
      return { art: "fehler", wort: "nicht erklärbar" };
  }
}

/** Eigene Titel je Prüfregel (Nummer vor dem Unterstrich), falls meta.regel keine Satzvorlage trägt. */
const TITEL: Record<string, string> = {
  P01: "Gleiche Zeilen kamen mehrfach vor.",
  P02: "Ein Verhältnis hat am Stichtag mehrere Zeitabschnitte.",
  P03: "Beginn und Ende waren vertauscht.",
  P04: "Im Geburtsdatum steht der Monat 13.",
  P05: "Das Geburtsdatum fehlt oder ist ungültig.",
  P06: "Das Alter kann nicht stimmen.",
  P07: "Sehr alte Beschäftigte, das Alter ist aber möglich.",
  P08: "Beginn oder Ende war kein gültiges Datum.",
  P09: "Der Beginn liegt nach dem Ende.",
  P10: "Bundesland oder Branche wurde leer geliefert.",
  P11: "Alte Branchencodes aus dem Jahr 2003.",
  P12: "Ein gelieferter Code steht in keiner Liste.",
  P13: "Gruppen aus dem Vormonat fehlen ganz.",
  P14: "Gruppen haben sich stark gegenüber dem Vormonat verändert.",
  P15: "Der Bestand fällt stark gegenüber dem Vormonat.",
  P16: "Verhältnisse des Vormonats fehlen in der Lieferung.",
  P17: "Die Lieferung hat deutlich mehr oder weniger Zeilen als die vorige.",
  P18: "Viele gleiche Codewechsel am selben Tag.",
  P19: "Mögliche Doppelmeldung bei neuen Verhältnissen.",
  P20: "Angaben einer Person passen nicht zusammen.",
  P21: "Teilsummen passen nicht zur Gesamtzahl.",
  P22: "Die Abrechnung der Sätze geht nicht auf.",
  P23: "Frühere Monate wären mit dieser Lieferung anders.",
  P24: "Die Lieferung deckt die Vormonate nicht ganz ab.",
};

// ---------------------------------------------------------------------------------------------------------------
// Maßnahmen in Alltagssprache

export interface MassnahmeLage {
  einstufung: Einstufung | null;
  anhalten: boolean;
  /** Steht im Rohtext eine Rückfrage an die Fachabteilung? */
  rueckfrage: boolean;
  /** Text in Klammern nach „keine (…)“, z. B. die Saisonbranchen. */
  klammer: string | null;
}

const FRAGT_NACH = "Die Fachabteilung soll das klären.";

/**
 * Ein Satz je Prüfregel (Nummer vor dem Unterstrich) statt des Rohtexts aus pruefung_treffer.massnahme, der
 * Kürzel wie „(E02)“, Pfeile oder Formeln trägt. Unbekannte Regeln fallen auf den Rohtext zurück.
 * Nur Regeln, deren Maßnahme nicht von Parametern abhängt. P04–P07, P10 und P11 (Ersatztag, Altersgrenzen,
 * „unbekannt“, Zielabschnitt) nehmen den gespeicherten Text des Treffers: Nach einer Live-Änderung der Regel
 * erklärt die Seite so die Regel, mit der gerechnet wurde, nicht eine alte Fassung (Review !51 Runde 2, Punkt 4).
 */
const MASSNAHME: Record<string, (l: MassnahmeLage) => string> = {
  P01: () => "Doppelte Zeilen sind zu einer zusammengefasst, jedes Verhältnis zählt einmal.",
  P03: () => "Beginn und Ende sind für die ganze Lieferung zurückgetauscht.",
  P13: () => "Der Monat ist angehalten, die Fachabteilung soll klären, warum die Gruppen fehlen.",
  P14: (l) =>
    l.einstufung === "nicht-erklaerbar"
      ? "Die Zahlen bleiben, wie sie geliefert sind. Die Fachabteilung soll die Veränderung erklären."
      : `Nichts zu tun, das ist die übliche Saison${l.klammer ? ` (${l.klammer.replace(/^Saison:\s*/, "")})` : ""}.`,
  P15: () => "Der Monat ist angehalten, bis jemand die Lieferung geprüft hat.",
  P16: (l) =>
    l.anhalten
      ? "Der Monat ist angehalten, bis die fehlenden Verhältnisse nachgeliefert sind."
      : "Nichts zu tun, es sind Einzelfälle wie Stornos.",
  P17: () => "Der Monat ist angehalten, bis jemand geprüft hat, ob die Lieferung vollständig ist.",
  P18: () => "Sie zählen wie geliefert. Die Fachabteilung soll den Wechsel erklären.",
  P19: (l) =>
    `Sie sind markiert und zählen mit, denn gezählt werden Verhältnisse, nicht Personen.${
      l.rueckfrage ? " Die Fachabteilung soll klären, ob es doppelte Meldungen sind." : ""
    }`,
  P23: (l) =>
    l.einstufung === "nicht-erklaerbar"
      ? `Der Unterschied steht als Revisionsbedarf im Bericht. ${FRAGT_NACH}`
      : "Der Unterschied steht als Revisionsbedarf im Bericht, veröffentlichte Zahlen bleiben.",
  P24: (l) =>
    `Nichts zu korrigieren, die Lieferung reicht nicht drei Monate zurück, etwa bei der ersten Lieferung.${
      l.rueckfrage ? ` ${FRAGT_NACH}` : ""
    }`,
};

/**
 * Rohtext als Satz: Klammern mit Regelkürzeln wie „(R5 ersatz:07-01)“ oder „(E03, R5)“ fallen weg, „u.“ wird „und“,
 * Pfeil als „Zugeordnet zu“, Großbuchstabe vorn, Punkt hinten.
 */
export function rohAlsSatz(roh: string): string {
  let s = roh
    .replace(/\s*\((?:[A-Z]\d+[^)]*)\)/g, "")
    .replace(/\bu\. /g, "und ")
    .split(/\s+/)
    .join(" ")
    .trim();
  if (!s) return "";
  if (s.startsWith("→")) s = `Zugeordnet zu${s.slice(1)}`;
  s = s.replaceAll("→", "zu");
  s = s[0].toUpperCase() + s.slice(1);
  return /[.!?)]$/.test(s) ? s : `${s}.`;
}

/** „Was wir tun“ als ein Satz in Alltagssprache; ohne Rohtext `null`. */
export function massnahmeSatz(
  t: { name: string; massnahme: string | null; einstufung: Einstufung | null; anhalten: boolean },
): string | null {
  const roh = t.massnahme?.trim();
  if (!roh) return null;
  const regel = MASSNAHME[t.name.split("_")[0] ?? ""];
  if (!regel) return rohAlsSatz(roh);
  return regel({
    einstufung: t.einstufung ?? "nicht-erklaerbar",
    anhalten: t.anhalten,
    rueckfrage: /Rückfrage|an die Fachabteilung/.test(roh),
    klammer: /^keine \((.+)\)/.exec(roh)?.[1] ?? null,
  });
}

/** „nicht erklärbar, wartet auf Antwort der Fachabteilung (R8)“, wenn eine offene Rückfrage dranhängt. */
export function wartetSatz(offeneRueckfragen: readonly string[] | undefined): string | null {
  return offeneRueckfragen?.length ? `wartet auf Antwort der Fachabteilung (${aufzaehlen(offeneRueckfragen)})` : null;
}

/** Titel einer Auffälligkeit: Satzvorlage der Regel, sonst eigener Titel, sonst der erste Satz der Beschreibung. */
export function trefferTitel(t: Pick<Treffer, "name" | "beschreibung" | "satz" | "anzahl" | "umfang">, lieferung: string): string {
  if (t.satz) {
    return t.satz
      .replaceAll("{anzahl}", formatZahl(t.anzahl))
      .replaceAll("{monat}", monatName(lieferung))
      .replaceAll("{umfang}", t.umfang ?? "");
  }
  const eigen = TITEL[t.name.split("_")[0] ?? ""];
  if (eigen) return eigen;
  const erster = t.beschreibung.split(/(?<=\.)\s/)[0] ?? t.beschreibung;
  return erster || t.name;
}

/** Steht der Umfang schon im Titel (Vorlage mit {umfang}), wird er nicht noch einmal gezeigt. */
export function umfangImTitel(t: Pick<Treffer, "satz">): boolean {
  return Boolean(t.satz?.includes("{umfang}"));
}

const EINSTUFUNG_RANG: Record<string, number> = { "nicht-erklaerbar": 0, "erklaert-datenproblem": 1, "erklaert-plausibel": 2 };

/** Nur Treffer mit Anzahl > 0: anhaltende zuerst, dann nicht erklärbar, dann nach Anzahl. */
export function sortiereTreffer(treffer: readonly Treffer[]): Treffer[] {
  return treffer
    .filter((t) => t.anzahl > 0)
    .sort(
      (a, b) =>
        Number(b.anhalten) - Number(a.anhalten) ||
        (EINSTUFUNG_RANG[a.einstufung ?? "nicht-erklaerbar"] ?? 3) - (EINSTUFUNG_RANG[b.einstufung ?? "nicht-erklaerbar"] ?? 3) ||
        b.anzahl - a.anzahl,
    );
}

/** Welche anhaltende Prüfung die Überschrift trägt: die, deren Zahl ein Mensch am leichtesten versteht. */
const HALT_VORRANG = ["verhaeltnisse_verschwunden", "bestand_vs_vormonat", "auspraegung_verschwunden", "zeilenzahl_vs_vormonat"];

export function haltTreffer(treffer: readonly Treffer[]): Treffer | null {
  const anhaltend = treffer.filter((t) => t.anhalten);
  const rang = (t: Treffer) => {
    const i = HALT_VORRANG.indexOf(t.art);
    return i < 0 ? HALT_VORRANG.length : i;
  };
  return [...anhaltend].sort((a, b) => rang(a) - rang(b) || b.anzahl - a.anzahl)[0] ?? null;
}

/** Überschrift eines angehaltenen Monats: Grund mit Zahl. */
export function haltSatz(t: Pick<Treffer, "art" | "anzahl" | "name" | "beschreibung" | "satz" | "umfang">, lieferung: string): string {
  const im = `Im ${monatName(lieferung)}`;
  const n = t.anzahl;
  const deshalb = "deshalb ist der Monat angehalten.";
  switch (t.art) {
    case "verhaeltnisse_verschwunden":
      return `${im} ${n === 1 ? "fehlt" : "fehlen"} ${verhaeltnisse(n)} des Vormonats, ${deshalb}`;
    case "bestand_vs_vormonat":
      return `${im} wären es ${verhaeltnisse(n)} weniger als im Vormonat, ${deshalb}`;
    case "auspraegung_verschwunden":
      return n === 1
        ? `${im} fehlt eine Gruppe ganz, die es im Vormonat noch gab, ${deshalb}`
        : `${im} fehlen ${formatZahl(n)} Gruppen ganz, die es im Vormonat noch gab, ${deshalb}`;
    case "zeilenzahl_vs_vormonat":
      return `${im} weicht die Lieferung um ${formatZahl(n)} ${n === 1 ? "Zeile" : "Zeilen"} von der vorigen ab, ${deshalb}`;
    default:
      return `${im} hält die Prüfung „${trefferTitel(t, lieferung).replace(/\.$/, "")}“ den Monat an.`;
  }
}

/** Überschrift eines Monats, der nicht angehalten ist: Bestand am Stichtag und Veränderung zum Vormonat. */
export function bestandSatz(lauf: Pick<Lauf, "lieferung" | "gezaehlt">, vormonat: Pick<Lauf, "lieferung" | "gezaehlt"> | null): string {
  const kopf = `Am ${stichtag(lauf.lieferung)} bestanden ${formatZahl(lauf.gezaehlt)} Beschäftigungsverhältnisse`;
  if (!vormonat) return `${kopf}.`;
  const d = lauf.gezaehlt - vormonat.gezaehlt;
  const vm = monatName(vormonat.lieferung);
  if (d === 0) return `${kopf}, gleich viele wie im ${vm}.`;
  return `${kopf}, ${formatZahl(Math.abs(d))} ${d > 0 ? "mehr" : "weniger"} als im ${vm}.`;
}

/** „425.151 gelesene Sätze = 387.180 gezählt + 36.308 nicht gezählt + 1.663 ausgeschlossen.“ (ohne Fortgeschriebene) */
export function abrechnungSatz(lauf: Pick<Lauf, "gelesen" | "gezaehlt" | "fortgeschrieben" | "nichtGezaehlt" | "ausgeschlossen">): string {
  return `${formatZahl(lauf.gelesen)} gelesene Sätze = ${formatZahl(lauf.gezaehlt - lauf.fortgeschrieben)} gezählt + ${formatZahl(lauf.nichtGezaehlt)} nicht gezählt + ${formatZahl(lauf.ausgeschlossen)} ausgeschlossen.`;
}

export function determinismusSatz(d: Determinismus): string {
  const kurz = d.hash.slice(0, 8);
  if (d.laeufe <= 1) return `Ein Lauf mit diesen Regeln, Ergebnis-Hash ${kurz}.`;
  if (d.hashes === 1) return `${formatZahl(d.laeufe)} Läufe mit diesen Regeln, alle mit demselben Ergebnis-Hash ${kurz}.`;
  return `${formatZahl(d.laeufe)} Läufe mit diesen Regeln, aber ${formatZahl(d.hashes)} verschiedene Ergebnis-Hashes.`;
}

/** Ein Satz je Berichtsmonat mit Revisionsbedarf. */
export function revisionSatz(r: Pick<Revision, "berichtsmonat" | "veroeffentlicht" | "aktuell" | "differenz" | "statusVorher">): string {
  const monat = monatName(r.berichtsmonat);
  const veroeffentlicht = r.statusVorher === "endgueltig";
  if (r.differenz === 0) return `Mit dieser Lieferung bliebe ${monat} gleich.`;
  const richtung = r.differenz < 0 ? "kleiner" : "größer";
  const bezug = veroeffentlicht ? "als veröffentlicht" : "als bisher gezeigt";
  const bleibt = veroeffentlicht
    ? "Die veröffentlichte Zahl bleibt stehen."
    : "Die bisher gezeigte Zahl bleibt stehen, weil jeder Monat nur aus seiner eigenen Lieferung gerechnet wird.";
  return `Mit dieser Lieferung wäre ${monat} um ${verhaeltnisse(Math.abs(r.differenz))} ${richtung} ${bezug} (${formatZahl(r.aktuell)} statt ${formatZahl(r.veroeffentlicht)}). ${bleibt}`;
}

function ursacheTeil(u: Ursache): string | null {
  const n = u.anzahl;
  const nv = verhaeltnisse(n);
  const ist = n === 1 ? "ist" : "sind";
  const wurde = n === 1 ? "wurde" : "wurden";
  switch (u.ursache) {
    case "nicht_mehr_enthalten":
      return `${nv} ${ist} in der neuen Lieferung nicht mehr enthalten`;
    case "rueckwirkende_abmeldung":
      return `${nv} ${wurde} rückwirkend abgemeldet`;
    case "nachmeldung":
      return `${nv} ${wurde} nachgemeldet`;
    case "merkmal_geaendert":
      return `bei ${nv} hat sich ein Merkmal geändert`;
    default:
      return `${nv}: ${u.ursache}`;
  }
}

/** „Gründe: 4.360 Verhältnisse sind … und 605 Verhältnisse wurden nachgemeldet.“; Ursachen mit 0 fallen weg. */
export function ursachenSatz(ursachen: readonly Ursache[]): string | null {
  const teile = [...ursachen]
    .filter((u) => u.anzahl > 0)
    .sort((a, b) => b.anzahl - a.anzahl)
    .map(ursacheTeil)
    .filter((t): t is string => t !== null);
  return teile.length ? `Gründe: ${aufzaehlen(teile)}.` : null;
}

/**
 * Kann der Befehl `veroeffentlichen` diesen Monat veröffentlichen? Spiegelt die Vorbedingungen der CLI: nicht schon
 * endgültig, kein anhaltender Treffer, keine Fortgeschriebenen (E07), alle Regeln und der Regelstand freigegeben.
 */
export function kannVeroeffentlichen(
  lauf: Pick<Lauf, "ergebnisStand" | "fortgeschrieben">,
  angehalten: boolean,
  lage: Pick<VeroeffentlichenLage, "regelnOhneFreigabe" | "regelstandFreigegeben">,
): boolean {
  return (
    lauf.ergebnisStand !== "endgueltig" &&
    !angehalten &&
    lauf.fortgeschrieben === 0 &&
    lage.regelnOhneFreigabe === 0 &&
    lage.regelstandFreigegeben
  );
}

/** „Der Monat bleibt vorläufig, bis die Rückfrage R3 beantwortet ist.“ */
export function bleibtVorlaeufigSatz(wartetAuf: readonly string[]): string {
  if (wartetAuf.length === 0) return "Der Monat bleibt vorläufig, bis die offene Frage geklärt ist.";
  return wartetAuf.length === 1
    ? `Der Monat bleibt vorläufig, bis die Rückfrage ${wartetAuf[0]} beantwortet ist.`
    : `Der Monat bleibt vorläufig, bis die Rückfragen ${aufzaehlen(wartetAuf)} beantwortet sind.`;
}

/** Ein Satz je Berichtsmonat, in dem sich nur die Gruppen verschieben. */
export function umschichtungSatz(r: Pick<Revision, "berichtsmonat">): string {
  return `Mit dieser Lieferung bliebe die Summe für ${monatName(r.berichtsmonat)} gleich, aber Verhältnisse verschieben sich zwischen den Gruppen.`;
}

// ---------------------------------------------------------------------------------------------------------------
// Beleg-Abfragen (Anzeige)

const BESTAND_FILTER = "zeitraum_art = 'Stichtag' AND variable = 'Beschaeftigungsverhaeltnisse'";

/** Bestand dieses Monats und des Vormonats, je mit dem Regelstand ihres maßgeblichen Laufs. */
export function sqlBestandMitVormonat(lauf: Lauf, vormonat: Lauf | null): string {
  const teil = (l: Lauf) => {
    const { von, bis } = monatsgrenzen(l.lieferung);
    return `(regelstand = ${literal(l.regelstand)} AND zeitraum_bis BETWEEN ${literal(von)} AND ${literal(bis)})`;
  };
  return [
    "SELECT to_char(zeitraum_bis, 'YYYY-MM') AS monat, sum(wert) AS beschaeftigungsverhaeltnisse",
    "FROM stat.stat_beschaeftigte",
    `WHERE regelsatz = ${literal(lauf.regelsatz)} AND ${BESTAND_FILTER}`,
    `  AND (${[vormonat, lauf].filter((l): l is Lauf => l !== null).map(teil).join("\n       OR ")})`,
    "GROUP BY 1 ORDER BY 1;",
  ].join("\n");
}

export function sqlKennzahlen(lauf: Pick<Lauf, "id" | "quelleId">): string {
  return [
    "SELECT lieferung, gelesen, gezaehlt, fortgeschrieben, nicht_gezaehlt, ausgeschlossen, ergebnis_status",
    "FROM meta.lauf",
    `WHERE id = ${literal(lauf.id)};`,
  ].join("\n");
}

export function sqlDeterminismus(lauf: Pick<Lauf, "lieferung" | "regelsatz" | "regelstand">): string {
  return [
    "SELECT count(*) AS laeufe, count(DISTINCT ergebnis_hash) AS hashes, min(ergebnis_hash) AS ergebnis_hash",
    "FROM meta.lauf",
    `WHERE lieferung = ${literal(lauf.lieferung)} AND regelsatz = ${literal(lauf.regelsatz)}`,
    `  AND regelstand = ${literal(lauf.regelstand)} AND status IN ${GUELTIG};`,
  ].join("\n");
}

/** Abfrage des Treffers (liefert alle gezeigten Angaben) und darunter die Prüfabfrage der Regel. */
export function sqlTreffer(lauf: Pick<Lauf, "id" | "quelleId">, t: Pick<Treffer, "regelId" | "ebene" | "belegSql">): string {
  const kopf = [
    "SELECT r.name, p.anzahl, p.umfang, coalesce(p.einstufung, 'nicht-erklaerbar') AS einstufung, p.massnahme, p.anhalten,",
    "       ARRAY(SELECT q.nr FROM meta.rueckfrage q WHERE q.antwort IS NULL",
    "             AND (q.nr = p.details ->> 'rueckfrage' OR q.regel_name = r.name)) AS offene_rueckfragen",
    "FROM meta.pruefung_treffer p JOIN meta.regel r ON r.id = p.regel_id",
    `WHERE p.lauf_id = ${literal(lauf.quelleId)} AND p.regel_id = ${literal(t.regelId)} AND p.ebene = ${literal(t.ebene)};`,
  ];
  return t.belegSql ? [...kopf, "", "-- Prüfabfrage der Regel, mit der die Anzahl gerechnet wurde:", t.belegSql.trim()].join("\n") : kopf.join("\n");
}

const UMGESCHICHTET =
  "EXISTS (SELECT 1 FROM meta.revision g WHERE g.lauf_id = r.lauf_id AND g.berichtsmonat = r.berichtsmonat AND g.gliederung <> 'insgesamt' AND g.differenz <> 0)";

export function sqlRevision(lauf: Pick<Lauf, "id" | "quelleId">, berichtsmonat: string): string {
  return [
    "SELECT r.berichtsmonat, r.veroeffentlicht, r.aktuell, r.differenz, r.status_vorher, u.ursache, u.anzahl,",
    `       ${UMGESCHICHTET} AS umgeschichtet`,
    "FROM meta.revision r",
    "LEFT JOIN meta.revision_ursache u ON u.lauf_id = r.lauf_id AND u.berichtsmonat = r.berichtsmonat",
    `WHERE r.lauf_id = ${literal(lauf.id)} AND r.gliederung = 'insgesamt' AND r.berichtsmonat = ${literal(berichtsmonat)}`,
    "ORDER BY u.anzahl DESC;",
  ].join("\n");
}

export function sqlKeineRevision(lauf: Pick<Lauf, "id" | "quelleId">): string {
  return [
    "SELECT count(*) AS monate_mit_revisionsbedarf",
    "FROM meta.revision r",
    `WHERE r.lauf_id = ${literal(lauf.id)} AND r.gliederung = 'insgesamt'`,
    `  AND (r.differenz <> 0 OR ${UMGESCHICHTET});`,
  ].join("\n");
}

/** Was der Befehl veroeffentlichen prüft: Regeln ohne Freigabe, Freigabe des Regelstands, offene Rückfragen. */
export function sqlVeroeffentlichen(lauf: Pick<Lauf, "id" | "quelleId" | "lieferung" | "regelsatz" | "regelstand">): string {
  const l = literal(lauf.lieferung);
  return [
    "SELECT (SELECT count(*) FROM meta.regel",
    `         WHERE regelsatz = ${literal(lauf.regelsatz)} AND aktiv AND freigegeben_von IS NULL`,
    `           AND gueltig_ab_lieferung <= ${l} AND (gueltig_bis_lieferung IS NULL OR gueltig_bis_lieferung >= ${l})) AS regeln_ohne_freigabe,`,
    "       EXISTS (SELECT 1 FROM meta.regelstand_freigabe",
    `               WHERE regelsatz = ${literal(lauf.regelsatz)} AND lieferung = ${l} AND regelstand = ${literal(lauf.regelstand)}) AS regelstand_freigegeben,`,
    `       (SELECT fortgeschrieben FROM meta.lauf WHERE id = ${literal(lauf.id)}) AS fortgeschrieben,`,
    `       (SELECT count(*) FROM meta.pruefung_treffer WHERE lauf_id = ${literal(lauf.quelleId)} AND anhalten) AS anhaltende_treffer;`,
  ].join("\n");
}

/** Bestand je Bundesland; ROLLUP liefert die Summenzeile (Bundesland leer) gleich mit. */
export function sqlRegionen(lauf: Pick<Lauf, "lieferung" | "regelsatz" | "regelstand">): string {
  const { von, bis } = monatsgrenzen(lauf.lieferung);
  return [
    "SELECT s.region, k.bezeichnung, sum(s.wert) AS beschaeftigungsverhaeltnisse",
    "FROM stat.stat_beschaeftigte s",
    "LEFT JOIN stat.klass_region k ON k.code = s.region AND k.ebene = 'bundesland'",
    "  AND k.gueltig_von <= s.zeitraum_bis AND (k.gueltig_bis IS NULL OR k.gueltig_bis >= s.zeitraum_bis)",
    `WHERE s.regelsatz = ${literal(lauf.regelsatz)} AND s.regelstand = ${literal(lauf.regelstand)}`,
    `  AND s.${BESTAND_FILTER.replace(" AND ", " AND s.")}`,
    `  AND s.zeitraum_bis BETWEEN ${literal(von)} AND ${literal(bis)}`,
    "GROUP BY ROLLUP ((s.region, k.bezeichnung))",
    "ORDER BY grouping(s.region), s.region = '0', 3 DESC;",
  ].join("\n");
}

// ---------------------------------------------------------------------------------------------------------------
// Leser

interface TrefferZeile {
  regel_id: number;
  name: string;
  art: string | null;
  beschreibung: string | null;
  satz: string | null;
  ebene: string;
  anzahl: string | number;
  umfang: string | null;
  einstufung: Einstufung;
  massnahme: string | null;
  anhalten: boolean;
  beleg_sql: string | null;
  offene_rueckfragen: string[] | null;
}

async function ladeTreffer(sql: Sql, laufId: number): Promise<Treffer[]> {
  const zeilen = await sql<TrefferZeile[]>`
    SELECT p.regel_id, r.name, r.art, r.beschreibung, r.parameter->>'satz' AS satz, p.ebene, p.anzahl, p.umfang,
           coalesce(p.einstufung, 'nicht-erklaerbar') AS einstufung, p.massnahme, p.anhalten, p.beleg_sql,
           ARRAY(SELECT q.nr FROM meta.rueckfrage q
                 WHERE q.antwort IS NULL AND (q.nr = p.details ->> 'rueckfrage' OR q.regel_name = r.name)
                 ORDER BY length(q.nr), q.nr) AS offene_rueckfragen
    FROM meta.pruefung_treffer p JOIN meta.regel r ON r.id = p.regel_id
    WHERE p.lauf_id = ${laufId} AND p.anzahl > 0`;
  return sortiereTreffer(
    zeilen.map((z) => ({
      regelId: z.regel_id,
      name: z.name,
      art: z.art ?? "",
      beschreibung: z.beschreibung ?? "",
      satz: z.satz,
      ebene: z.ebene,
      anzahl: zahl(z.anzahl),
      umfang: z.umfang,
      einstufung: z.einstufung,
      massnahme: z.massnahme,
      anhalten: z.anhalten,
      belegSql: z.beleg_sql,
      offeneRueckfragen: z.offene_rueckfragen ?? [],
    })),
  );
}

async function ladeRevisionen(sql: Sql, laufId: number): Promise<Revision[]> {
  const [revisionen, ursachen] = await Promise.all([
    sql<
      { berichtsmonat: string; veroeffentlicht: string; aktuell: string; differenz: string; status_vorher: string; umgeschichtet: boolean }[]
    >`
      SELECT r.berichtsmonat, r.veroeffentlicht, r.aktuell, r.differenz, r.status_vorher,
             EXISTS (SELECT 1 FROM meta.revision g WHERE g.lauf_id = r.lauf_id AND g.berichtsmonat = r.berichtsmonat
                     AND g.gliederung <> 'insgesamt' AND g.differenz <> 0) AS umgeschichtet
      FROM meta.revision r WHERE r.lauf_id = ${laufId} AND r.gliederung = 'insgesamt' ORDER BY r.berichtsmonat`,
    sql<{ berichtsmonat: string; ursache: string; anzahl: string }[]>`
      SELECT berichtsmonat, ursache, anzahl FROM meta.revision_ursache WHERE lauf_id = ${laufId}`,
  ]);
  return revisionen.map((r) => ({
    berichtsmonat: r.berichtsmonat,
    veroeffentlicht: zahl(r.veroeffentlicht),
    aktuell: zahl(r.aktuell),
    differenz: zahl(r.differenz),
    statusVorher: r.status_vorher,
    umgeschichtet: Boolean(r.umgeschichtet),
    ursachen: ursachen
      .filter((u) => u.berichtsmonat === r.berichtsmonat)
      .map((u) => ({ ursache: u.ursache, anzahl: zahl(u.anzahl) })),
  }));
}

async function ladeRegionen(sql: Sql, lauf: Lauf): Promise<Region[]> {
  const { von, bis } = monatsgrenzen(lauf.lieferung);
  const zeilen = await sql<{ region: string; bezeichnung: string | null; anzahl: string }[]>`
    SELECT s.region, k.bezeichnung, sum(s.wert) AS anzahl
    FROM stat.stat_beschaeftigte s
    LEFT JOIN stat.klass_region k ON k.code = s.region AND k.ebene = 'bundesland'
      AND k.gueltig_von <= s.zeitraum_bis AND (k.gueltig_bis IS NULL OR k.gueltig_bis >= s.zeitraum_bis)
    WHERE s.regelsatz = ${lauf.regelsatz} AND s.regelstand = ${lauf.regelstand}
      AND s.zeitraum_art = 'Stichtag' AND s.variable = 'Beschaeftigungsverhaeltnisse'
      AND s.zeitraum_bis BETWEEN ${von} AND ${bis}
    GROUP BY s.region, k.bezeichnung
    ORDER BY s.region = '0', 3 DESC`;
  return zeilen.map((z) => ({
    code: z.region,
    name: z.region === "0" ? "unbekannt" : (z.bezeichnung ?? `Code ${z.region}`),
    anzahl: zahl(z.anzahl),
  }));
}

async function ladeDeterminismus(sql: Sql, lauf: Lauf): Promise<Determinismus> {
  const [z] = await sql<{ laeufe: string; hashes: string; ergebnis_hash: string | null }[]>`
    SELECT count(*) AS laeufe, count(DISTINCT ergebnis_hash) AS hashes, min(ergebnis_hash) AS ergebnis_hash
    FROM meta.lauf
    WHERE lieferung = ${lauf.lieferung} AND regelsatz = ${lauf.regelsatz} AND regelstand = ${lauf.regelstand}
      AND status IN ('fertig', 'unveraendert')`;
  return { laeufe: zahl(z?.laeufe), hashes: zahl(z?.hashes), hash: z?.ergebnis_hash ?? "" };
}

async function ladeVeroeffentlichen(sql: Sql, lauf: Lauf, treffer: readonly Treffer[]): Promise<VeroeffentlichenLage> {
  const [[z], e07] = await Promise.all([
    sql<{ regeln_ohne_freigabe: string; regelstand_freigegeben: boolean }[]>`
      SELECT (SELECT count(*) FROM meta.regel
               WHERE regelsatz = ${lauf.regelsatz} AND aktiv AND freigegeben_von IS NULL
                 AND gueltig_ab_lieferung <= ${lauf.lieferung}
                 AND (gueltig_bis_lieferung IS NULL OR gueltig_bis_lieferung >= ${lauf.lieferung})) AS regeln_ohne_freigabe,
             EXISTS (SELECT 1 FROM meta.regelstand_freigabe
                     WHERE regelsatz = ${lauf.regelsatz} AND lieferung = ${lauf.lieferung}
                       AND regelstand = ${lauf.regelstand}) AS regelstand_freigegeben`,
    lauf.fortgeschrieben > 0
      ? sql<{ nr: string }[]>`
          SELECT nr FROM meta.rueckfrage
          WHERE antwort IS NULL AND regel_name LIKE 'E07%' AND lieferungen LIKE ${`%${lauf.lieferung}%`}
          ORDER BY length(nr), nr`
      : Promise.resolve([] as { nr: string }[]),
  ]);
  const ausTreffern = treffer.filter((t) => t.anhalten).flatMap((t) => t.offeneRueckfragen ?? []);
  const wartetAuf = [...new Set([...e07.map((r) => r.nr), ...ausTreffern])].sort(
    (a, b) => a.length - b.length || a.localeCompare(b),
  );
  return {
    regelnOhneFreigabe: zahl(z?.regeln_ohne_freigabe),
    regelstandFreigegeben: Boolean(z?.regelstand_freigegeben),
    wartetAuf,
  };
}

async function hatLauf(sql: Sql, lieferungen: string[], regelsatz: string): Promise<Set<string>> {
  const zeilen = await sql<{ lieferung: string }[]>`
    SELECT DISTINCT lieferung FROM meta.lauf
    WHERE regelsatz = ${regelsatz} AND lieferung IN ${sql(lieferungen)} AND status IN ('fertig', 'unveraendert')`;
  return new Set(zeilen.map((z) => z.lieferung));
}

/** Regelsatz aus der Adresse: nur „v1“ oder „v2“, alles andere gilt als „v1“. */
export { regelsatzAus } from "./navigation";

/** Alles für die Seite eines Monats; `null`, wenn es für den Monat keinen Lauf gibt. */
export async function ladeLaufDetail(sql: Sql, lieferung: string, regelsatz = "v1"): Promise<LaufDetail | null> {
  const davor = verschieben(lieferung, -1);
  const danach = verschieben(lieferung, 1);
  const [lauf, vormonat, nachbarn] = await Promise.all([
    ladeMassgeblichenLauf(sql, lieferung, regelsatz),
    ladeMassgeblichenLauf(sql, davor, regelsatz),
    hatLauf(sql, [davor, danach], regelsatz),
  ]);
  if (!lauf) return null;
  const [treffer, revisionen, regionen, determinismus] = await Promise.all([
    ladeTreffer(sql, lauf.quelleId),
    ladeRevisionen(sql, lauf.id),
    ladeRegionen(sql, lauf),
    ladeDeterminismus(sql, lauf),
  ]);
  const veroeffentlichen = await ladeVeroeffentlichen(sql, lauf, treffer);
  return { lauf, veroeffentlichen, vormonat, davor: nachbarn.has(davor), danach: nachbarn.has(danach), treffer, revisionen, regionen, determinismus };
}

export function leseLaufDetail(lieferung: string, regelsatz = "v1"): Promise<Lesung<LaufDetail | null>> {
  return lies((sql) => ladeLaufDetail(sql, lieferung, regelsatz));
}
