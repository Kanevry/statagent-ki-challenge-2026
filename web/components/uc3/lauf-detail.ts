import { formatZahl } from "@kic/ui/bausteine";
import { literal } from "./beleg";
import { lies, type Lesung, type Sql } from "./db";
import { ladeMassgeblichenLauf } from "./laeufe";
import { monatName, monatsgrenzen, stichtag, verschieben } from "./monat";
import type { Lauf } from "./typen";
import { bestandFilter, bestandSpalte, imZeitraumText, type ZeitraumArt } from "./zeitraum";

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
  /** meta.pruefung_treffer.details: Anteil, fehlende Gruppen, Rückfrage der Prüfung. */
  details?: TrefferDetails | null;
}

/** Felder aus meta.pruefung_treffer.details, die die Seite liest; alles andere bleibt unbeachtet. */
export interface TrefferDetails {
  anteil?: number;
  /** P15/P17: Wert dieses Monats und des Vormonats (bei P16 steht in „vormonat“ der Monat als Text). */
  aktuell?: number;
  vormonat?: number | string;
  rueckfrage?: string;
  auspraegungen?: { code: string; gliederung: string; aktuell: number; vormonat: number }[];
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
  /** Qualifikationen mit freiem Dienstvertrag (stat.klass_qualifikation), für „alle freien Dienstverträge“. */
  fdCodes: string[];
}

function zahl(wert: unknown): number {
  const n = Number(wert ?? 0);
  return Number.isFinite(n) ? n : 0;
}

// ---------------------------------------------------------------------------------------------------------------
// Sätze

/** „1 Beschäftigungsverhältnis“, „2 Beschäftigungsverhältnisse“ (docs/sprache.md: nie „Verhältnis“ allein). */
export function verhaeltnisse(n: number): string {
  return `${formatZahl(n)} ${n === 1 ? "Beschäftigungsverhältnis" : "Beschäftigungsverhältnisse"}`;
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
  P02: "Ein Beschäftigungsverhältnis hat am Stichtag mehrere Zeitabschnitte.",
  P03: "Beginn und Ende waren vertauscht.",
  P04: "Im Geburtsdatum steht der Monat 13.",
  P05: "Das Geburtsdatum fehlt oder ist ungültig.",
  P06: "Das Alter kann nicht stimmen.",
  P07: "Menschen ab 75 Jahren, das Alter ist möglich.",
  P08: "Beginn oder Ende war kein gültiges Datum.",
  P09: "Der Beginn liegt nach dem Ende.",
  P10: "Bundesland oder Branche wurde leer geliefert.",
  P11: "Alte Branchencodes aus dem Jahr 2003.",
  P12: "Ein gelieferter Code steht in keiner Liste.",
  P13: "Gruppen aus dem Vormonat fehlen ganz.",
  P14: "Gruppen haben sich stark gegenüber dem Vormonat verändert.",
  P15: "Der Bestand fällt stark gegenüber dem Vormonat.",
  P16: "Beschäftigungsverhältnisse des Vormonats fehlen in der Lieferung.",
  P17: "Die Zeilenzahl weicht deutlich von der vorigen Lieferung ab.",
  P18: "Viele gleiche Codewechsel am selben Tag.",
  P19: "Mögliche Doppelmeldung bei neuen Beschäftigungsverhältnissen.",
  P20: "Angaben einer Person passen nicht zusammen.",
  P21: "Teilsummen passen nicht zur Gesamtzahl.",
  P22: "Die Abrechnung der Zeilen geht nicht auf.",
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
  /** Nummer der offenen Rückfrage, an der die Prüfung hängt (z. B. „R3“), sonst null. */
  rueckfrageNr: string | null;
  /** Fehlen im selben Monat ganze Gruppen (P13), wie viele davon und wie sie heißen. */
  fehlendeGruppen: FehlendeGruppen | null;
}

/** Ganze Gruppen, die im Monat fehlen (P13), mit der Zahl aus dem Vormonat. */
export interface FehlendeGruppen {
  anzahl: number;
  /** „alle freien Dienstverträge“, „die freien Dienstverträge (ArbeiterFD)“ oder „2 Gruppen (X, Y)“. */
  wort: string;
  /** Fehlen genau alle Qualifikationen mit freiem Dienstvertrag laut stat.klass_qualifikation? */
  alleFreienDienstvertraege: boolean;
  /** Fehlen nur Qualifikationen mit freiem Dienstvertrag (alle oder ein Teil)? */
  nurFreieDienstvertraege: boolean;
}

/**
 * Fehlende Gruppen aus einer P13-Prüfung des Monats; ohne P13 oder ohne Angaben null. `fdCodes` sind die Codes mit
 * freier_dienstvertrag aus stat.klass_qualifikation: „alle“ steht nur, wenn genau diese fehlen (Review !77, Punkt 2).
 */
export function fehlendeGruppen(
  treffer: readonly Pick<Treffer, "art" | "details">[],
  fdCodes: readonly string[] = [],
): FehlendeGruppen | null {
  const p13 = treffer.find((t) => t.art === "auspraegung_verschwunden" && t.details?.auspraegungen?.length);
  const liste = p13?.details?.auspraegungen ?? [];
  if (liste.length === 0) return null;
  const anzahl = liste.reduce((s, a) => s + (Number(a.vormonat) || 0), 0);
  const fd = new Set(fdCodes);
  const nurFd = fd.size > 0 && liste.every((a) => a.gliederung === "qualifikation" && fd.has(a.code));
  const alleFd = nurFd && [...fd].every((code) => liste.some((a) => a.code === code));
  const codes = liste.map((a) => a.code).join(", ");
  return {
    anzahl,
    alleFreienDienstvertraege: alleFd,
    nurFreieDienstvertraege: nurFd,
    wort: alleFd
      ? "alle freien Dienstverträge"
      : nurFd
        ? `die freien Dienstverträge (${codes})`
        : `${formatZahl(liste.length)} ${liste.length === 1 ? "Gruppe" : "Gruppen"} (${codes})`,
  };
}

/** Rückfrage einer Prüfung: aus details, sonst die erste offene; „neu“ und Ähnliches zählen nicht. */
function rueckfrageAus(t: Pick<Treffer, "details" | "offeneRueckfragen">): string | null {
  const kandidaten = [t.details?.rueckfrage, ...(t.offeneRueckfragen ?? [])];
  return kandidaten.find((nr): nr is string => typeof nr === "string" && /^R\d+$/.test(nr)) ?? null;
}

/** Ein Haltesatz für jede anhaltende Prüfung: dieselbe Bedingung wie unter „So geht es weiter“. */
function angehaltenBis(l: MassnahmeLage, sonst: string): string {
  return l.rueckfrageNr ? `Der Monat ist angehalten, bis die Fachabteilung Rückfrage ${l.rueckfrageNr} beantwortet.` : sonst;
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
  P01: () => "Doppelte Zeilen sind zu einer zusammengefasst, jedes Beschäftigungsverhältnis zählt einmal.",
  P03: () => "Beginn und Ende sind für die ganze Lieferung zurückgetauscht.",
  P13: (l) => angehaltenBis(l, "Der Monat ist angehalten, die Fachabteilung soll klären, warum die Gruppen fehlen."),
  P14: (l) =>
    l.einstufung === "nicht-erklaerbar"
      ? "Die Zahlen bleiben, wie sie geliefert sind. Die Fachabteilung soll die Veränderung erklären."
      : `Nichts zu tun, das ist die übliche Saison${l.klammer ? ` (${l.klammer.replace(/^Saison:\s*/, "")})` : ""}.`,
  P15: (l) => angehaltenBis(l, "Der Monat ist angehalten, bis jemand die Lieferung geprüft hat."),
  P16: (l) =>
    l.anhalten
      ? angehaltenBis(l, "Der Monat ist angehalten, bis die fehlenden Beschäftigungsverhältnisse nachgeliefert sind.")
      : l.fehlendeGruppen
        ? `${formatZahl(l.fehlendeGruppen.anzahl)} davon sind ${l.fehlendeGruppen.nurFreieDienstvertraege ? "die fehlenden freien Dienstverträge" : `die fehlenden ${l.fehlendeGruppen.wort}`}, die übrigen sind Einzelfälle wie Stornos.`
        : "Nichts zu tun, es sind Einzelfälle wie Stornos.",
  P17: (l) => angehaltenBis(l, "Der Monat ist angehalten, bis jemand geprüft hat, ob die Lieferung vollständig ist."),
  P18: () => "Sie zählen wie geliefert. Die Fachabteilung soll den Wechsel erklären.",
  P19: (l) =>
    `Sie sind markiert und zählen mit, denn gezählt werden Beschäftigungsverhältnisse, nicht Personen.${
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
  t: {
    name: string;
    massnahme: string | null;
    einstufung: Einstufung | null;
    anhalten: boolean;
    offeneRueckfragen?: string[];
    details?: TrefferDetails | null;
  },
  kontext: { fehlendeGruppen?: FehlendeGruppen | null } = {},
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
    rueckfrageNr: rueckfrageAus(t),
    fehlendeGruppen: kontext.fehlendeGruppen ?? null,
  });
}

/** „nicht erklärbar, wartet auf Antwort der Fachabteilung (R8)“, wenn eine offene Rückfrage dranhängt. */
export function wartetSatz(offeneRueckfragen: readonly string[] | undefined): string | null {
  return offeneRueckfragen?.length ? `wartet auf Antwort der Fachabteilung (${aufzaehlen(offeneRueckfragen)})` : null;
}

/**
 * Die Vorlage von P17 lässt die Richtung offen, „345.078 / 434.104 Zeilen gegen 2025-09 (-20,5 %)“ im Umfang kennt sie.
 * Ohne Prozentangabe, etwa in der Tabelle über alle Monate, bleibt der offene Wortlaut. meta.regel bleibt unberührt.
 */
function mitRichtung(satz: string, umfang: string | null): string {
  const prozent = umfang?.match(/\(([-−]?)\d[\d.,]*\s*%\)/);
  if (!prozent) return satz;
  return satz.replace("deutlich mehr oder weniger", prozent[1] ? "deutlich weniger" : "deutlich mehr");
}

/** Titel einer Auffälligkeit: Satzvorlage der Regel, sonst eigener Titel, sonst der erste Satz der Beschreibung. */
export function trefferTitel(t: Pick<Treffer, "name" | "beschreibung" | "satz" | "anzahl" | "umfang">, lieferung: string): string {
  if (t.satz) {
    return mitRichtung(t.satz, t.umfang)
      .replaceAll("{anzahl}", formatZahl(t.anzahl))
      .replaceAll("{monat}", monatName(lieferung))
      .replaceAll("{umfang}", t.umfang ?? "");
  }
  const eigen = TITEL[t.name.split("_")[0] ?? ""];
  if (eigen) return eigen;
  const erster = t.beschreibung.split(/(?<=\.)\s/)[0] ?? t.beschreibung;
  return erster || t.name;
}

/** Klartext einer Prüfung ohne Monatsbezug und ohne Punkt am Ende, z. B. „Teilsummen passen nicht zur Gesamtzahl“. */
export function pruefungTitel(name: string): string {
  return trefferTitel({ name, beschreibung: "", satz: null, anzahl: 0, umfang: null }, "").replace(/\.$/, "");
}

/**
 * Titel ohne die Klammer mit Messwerten (UI-Regie v1): Steht „({umfang})“ in der Satzvorlage, endet der Titel mit
 * dem Satz davor, und die Messwerte stehen getrennt für die aufgeklappte Zeile.
 */
export function titelUndMesswerte(
  t: Pick<Treffer, "name" | "beschreibung" | "satz" | "anzahl" | "umfang">,
  lieferung: string,
): { titel: string; messwerte: string | null } {
  if (t.satz?.includes("({umfang})")) {
    const titel = trefferTitel({ ...t, satz: t.satz.replace(/\s*\(\{umfang\}\)/, "") }, lieferung);
    return { titel, messwerte: t.umfang?.trim() || null };
  }
  return { titel: trefferTitel(t, lieferung), messwerte: null };
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

const ORDINAL: Record<number, string> = { 2: "zweite", 3: "dritte", 4: "vierte", 5: "fünfte", 6: "sechste", 7: "siebte", 8: "achte", 9: "neunte", 10: "zehnte" };

/** „jedes fünfte“ für einen Anteil nahe 1/n (n 2 bis 10), sonst „23 Prozent der“; ohne Anteil null. */
export function anteilWort(anteil: number | undefined | null): string | null {
  if (typeof anteil !== "number" || !(anteil > 0) || anteil >= 1) return null;
  const n = Math.round(1 / anteil);
  if (ORDINAL[n] && Math.abs(anteil * n - 1) < 0.05) return `jedes ${ORDINAL[n]}`;
  return `${formatZahl(Math.round(anteil * 100))} Prozent der`;
}

/**
 * Überschrift eines angehaltenen Monats: Grund mit Zahl und „das heißt“ (docs/sprache.md, Regel 3), dann ein eigener
 * Satz „Deshalb ist der Monat angehalten.“
 */
export function haltSatz(
  t: Pick<Treffer, "art" | "anzahl" | "name" | "beschreibung" | "satz" | "umfang"> & { details?: TrefferDetails | null },
  lieferung: string,
  fdCodes: readonly string[] = [],
): string {
  const im = `Im ${monatName(lieferung)}`;
  const vm = monatName(verschieben(lieferung, -1));
  const n = t.anzahl;
  const deshalb = "Deshalb ist der Monat angehalten.";
  switch (t.art) {
    case "verhaeltnisse_verschwunden": {
      const anteil = anteilWort(t.details?.anteil);
      if (anteil?.startsWith("jedes")) {
        return `${im} fehlt ${anteil} Beschäftigungsverhältnis aus dem ${vm}, zusammen ${formatZahl(n)}. ${deshalb}`;
      }
      if (anteil) return `${im} fehlen ${anteil} Beschäftigungsverhältnisse aus dem ${vm}, zusammen ${formatZahl(n)}. ${deshalb}`;
      return `${im} ${n === 1 ? "fehlt" : "fehlen"} ${verhaeltnisse(n)} aus dem ${vm}. ${deshalb}`;
    }
    case "bestand_vs_vormonat":
      return `${im} wären es ${verhaeltnisse(n)} weniger als im ${vm}. ${deshalb}`;
    case "auspraegung_verschwunden": {
      const g = fehlendeGruppen([t], fdCodes);
      if (g?.alleFreienDienstvertraege) return `${im} fehlen ${g.wort} (${vm}: ${formatZahl(g.anzahl)}). ${deshalb}`;
      if (g?.nurFreieDienstvertraege) {
        const codes = g.wort.replace(/^die freien Dienstverträge /, "");
        return `${im} fehlen freie Dienstverträge, im ${vm} waren es ${formatZahl(g.anzahl)} ${codes}. ${deshalb}`;
      }
      if (g) return `${im} fehlen ${g.wort} ganz, die es im ${vm} noch gab. ${deshalb}`;
      return n === 1
        ? `${im} fehlt eine Gruppe ganz, die es im ${vm} noch gab. ${deshalb}`
        : `${im} fehlen ${formatZahl(n)} Gruppen ganz, die es im ${vm} noch gab. ${deshalb}`;
    }
    case "zeilenzahl_vs_vormonat": {
      const r = richtung(t);
      const art = r === "kleiner" ? "weniger" : r === "groesser" ? "mehr" : null;
      return art
        ? `${im} hat die Lieferung ${formatZahl(n)} ${n === 1 ? "Zeile" : "Zeilen"} ${art} als die vorige. ${deshalb}`
        : `${im} weicht die Lieferung um ${formatZahl(n)} ${n === 1 ? "Zeile" : "Zeilen"} von der vorigen ab. ${deshalb}`;
    }
    default:
      return `${im} hält die Prüfung „${trefferTitel(t, lieferung).replace(/\.$/, "")}“ den Monat an.`;
  }
}

/** Richtung einer Mengen-Prüfung aus details (aktuell gegen vormonat), sonst null. */
function richtung(t: { details?: TrefferDetails | null }): "kleiner" | "groesser" | null {
  const a = t.details?.aktuell;
  const v = t.details?.vormonat;
  if (typeof a !== "number" || typeof v !== "number" || a === v) return null;
  return a < v ? "kleiner" : "groesser";
}

/** Haltegrund in wenigen Wörtern für die Monatsübersicht („jedes fünfte fehlt“, „freie Dienstverträge fehlen“). */
export function haltKurz(
  t: Pick<Treffer, "art" | "anzahl"> & { details?: TrefferDetails | null },
  fdCodes: readonly string[] = [],
): string {
  switch (t.art) {
    case "verhaeltnisse_verschwunden": {
      const anteil = anteilWort(t.details?.anteil);
      return anteil?.startsWith("jedes") ? `${anteil} Beschäftigungsverhältnis fehlt` : "Beschäftigungsverhältnisse fehlen";
    }
    case "auspraegung_verschwunden": {
      const g = fehlendeGruppen([t], fdCodes);
      return g?.nurFreieDienstvertraege ? "freie Dienstverträge fehlen" : "ganze Gruppen fehlen";
    }
    case "bestand_vs_vormonat":
      return "Bestand stark gesunken";
    case "zeilenzahl_vs_vormonat":
      return richtung(t) === "groesser" ? "Lieferung deutlich größer" : richtung(t) === "kleiner" ? "Lieferung deutlich kleiner" : "Lieferung deutlich anders";
    default:
      return "eine Prüfung hält an";
  }
}

/** Überschrift eines Monats, der nicht angehalten ist: Bestand (Stichtag oder ganzes Monat) und Veränderung zum Vormonat. */
export function bestandSatz(lauf: Pick<Lauf, "lieferung" | "gezaehlt" | "zeitraumArt">, vormonat: Pick<Lauf, "lieferung" | "gezaehlt"> | null): string {
  const wann = lauf.zeitraumArt === "Monat" ? `Im ${monatName(lauf.lieferung)}` : `Am ${stichtag(lauf.lieferung)}`;
  const kopf = `${wann} bestanden ${formatZahl(lauf.gezaehlt)} Beschäftigungsverhältnisse`;
  if (!vormonat) return `${kopf}.`;
  const d = lauf.gezaehlt - vormonat.gezaehlt;
  const vm = monatName(vormonat.lieferung);
  if (d === 0) return `${kopf}, gleich viele wie im ${vm}.`;
  return `${kopf}, ${formatZahl(Math.abs(d))} ${d > 0 ? "mehr" : "weniger"} als im ${vm}.`;
}

/** Gezählt aus der Lieferung selbst, ohne die aus dem Vormonat übernommenen (E07). */
export function ausLieferung(lauf: Pick<Lauf, "gezaehlt" | "fortgeschrieben">): number {
  return lauf.gezaehlt - lauf.fortgeschrieben;
}

/** „425.151 gelesene Zeilen = 387.180 gezählt + 36.308 nicht gezählt + 1.663 ausgeschlossen.“ (ohne Übernommene) */
export function abrechnungSatz(
  lauf: Pick<Lauf, "gelesen" | "gezaehlt" | "fortgeschrieben" | "nichtGezaehlt" | "ausgeschlossen">,
  gehtAuf = true,
): string {
  const teile = `${formatZahl(ausLieferung(lauf))} gezählt + ${formatZahl(lauf.nichtGezaehlt)} nicht gezählt + ${formatZahl(lauf.ausgeschlossen)} ausgeschlossen`;
  return gehtAuf
    ? `${formatZahl(lauf.gelesen)} gelesene Zeilen = ${teile}.`
    : `${formatZahl(lauf.gelesen)} gelesene Zeilen ≠ ${teile}. Die Abrechnung geht nicht auf.`;
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
    ? `Der Monat bleibt vorläufig, bis die Fachabteilung Rückfrage ${wartetAuf[0]} beantwortet.`
    : `Der Monat bleibt vorläufig, bis die Fachabteilung die Rückfragen ${aufzaehlen(wartetAuf)} beantwortet.`;
}

/**
 * Der eine Weg weiter für einen angehaltenen oder fortgeschriebenen Monat: was wir übernehmen (E07) und worauf der
 * Monat wartet. „Wir übernehmen 77.746 Beschäftigungsverhältnisse aus der Lieferung September 2025 (Regel E07). Der
 * Monat bleibt vorläufig, bis die Fachabteilung Rückfrage R3 beantwortet.“
 */
export function weiterSatz(lauf: Pick<Lauf, "lieferung" | "fortgeschrieben">, wartetAuf: readonly string[]): string {
  const bleibt = bleibtVorlaeufigSatz(wartetAuf);
  if (lauf.fortgeschrieben <= 0) return bleibt;
  const vm = monatName(verschieben(lauf.lieferung, -1));
  return `Wir übernehmen ${verhaeltnisse(lauf.fortgeschrieben)} aus der Lieferung ${vm} (Regel E07). ${bleibt}`;
}

/** Ein Satz je Berichtsmonat, in dem sich nur die Gruppen verschieben. */
export function umschichtungSatz(r: Pick<Revision, "berichtsmonat">): string {
  return `Mit dieser Lieferung bliebe die Summe für ${monatName(r.berichtsmonat)} gleich, aber Beschäftigungsverhältnisse verschieben sich zwischen den Gruppen.`;
}

// ---------------------------------------------------------------------------------------------------------------
// Beleg-Abfragen (Anzeige)

/** Bestand dieses Monats und des Vormonats, je mit dem Regelstand ihres maßgeblichen Laufs. */
export function sqlBestandMitVormonat(lauf: Lauf, vormonat: Lauf | null): string {
  const teil = (l: Lauf) => {
    const { von, bis } = monatsgrenzen(l.lieferung);
    return `(regelstand = ${literal(l.regelstand)} AND zeitraum_bis BETWEEN ${literal(von)} AND ${literal(bis)})`;
  };
  return [
    "SELECT to_char(zeitraum_bis, 'YYYY-MM') AS monat, sum(wert) AS beschaeftigungsverhaeltnisse",
    "FROM stat.stat_beschaeftigte",
    `WHERE regelsatz = ${literal(lauf.regelsatz)} AND ${bestandFilter(lauf.zeitraumArt)}`,
    `  AND (${[vormonat, lauf].filter((l): l is Lauf => l !== null).map(teil).join("\n       OR ")})`,
    "GROUP BY 1 ORDER BY 1;",
  ].join("\n");
}

export function sqlKennzahlen(lauf: Pick<Lauf, "id" | "quelleId" | "zeitraumArt">): string {
  return [
    "SELECT lieferung, gezaehlt - fortgeschrieben AS aus_der_lieferung, fortgeschrieben AS uebernommen,",
    `       gezaehlt AS ${bestandSpalte(lauf.zeitraumArt)}, gelesen, nicht_gezaehlt, ausgeschlossen, ergebnis_status`,
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
    "       p.details,",
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
export function sqlRegionen(lauf: Pick<Lauf, "lieferung" | "regelsatz" | "regelstand" | "zeitraumArt">): string {
  const { von, bis } = monatsgrenzen(lauf.lieferung);
  return [
    "SELECT s.region, k.bezeichnung, sum(s.wert) AS beschaeftigungsverhaeltnisse",
    "FROM stat.stat_beschaeftigte s",
    "LEFT JOIN stat.klass_region k ON k.code = s.region AND k.ebene = 'bundesland'",
    "  AND k.gueltig_von <= s.zeitraum_bis AND (k.gueltig_bis IS NULL OR k.gueltig_bis >= s.zeitraum_bis)",
    `WHERE s.regelsatz = ${literal(lauf.regelsatz)} AND s.regelstand = ${literal(lauf.regelstand)}`,
    `  AND ${bestandFilter(lauf.zeitraumArt, "s.")}`,
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
  details: TrefferDetails | null;
}

async function ladeTreffer(sql: Sql, laufId: number, art: ZeitraumArt): Promise<Treffer[]> {
  const zeilen = await sql<TrefferZeile[]>`
    SELECT p.regel_id, r.name, r.art, r.beschreibung, r.parameter->>'satz' AS satz, p.ebene, p.anzahl, p.umfang,
           coalesce(p.einstufung, 'nicht-erklaerbar') AS einstufung, p.massnahme, p.anhalten, p.beleg_sql, p.details,
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
      satz: z.satz === null ? null : imZeitraumText(z.satz, art),
      ebene: z.ebene,
      anzahl: zahl(z.anzahl),
      umfang: z.umfang === null ? null : imZeitraumText(z.umfang, art),
      einstufung: z.einstufung,
      massnahme: z.massnahme === null ? null : imZeitraumText(z.massnahme, art),
      anhalten: z.anhalten,
      belegSql: z.beleg_sql === null ? null : imZeitraumText(z.beleg_sql, art),
      offeneRueckfragen: z.offene_rueckfragen ?? [],
      details: z.details ?? null,
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
      AND s.zeitraum_art = ${lauf.zeitraumArt} AND s.variable = 'Beschaeftigungsverhaeltnisse'
      AND s.zeitraum_bis BETWEEN ${von} AND ${bis}
    GROUP BY s.region, k.bezeichnung
    ORDER BY s.region = '0', 3 DESC`;
  return zeilen.map((z) => ({
    code: z.region,
    name: z.region === "0" ? "unbekannt" : (z.bezeichnung ?? `Code ${z.region}`),
    anzahl: zahl(z.anzahl),
  }));
}

/** Codes der Qualifikationen mit freiem Dienstvertrag; ältere Stände ohne Spalte ergeben eine leere Liste. */
export async function ladeFdCodes(sql: Sql): Promise<string[]> {
  try {
    const zeilen = await sql<{ code: string }[]>`
      SELECT code FROM stat.klass_qualifikation WHERE freier_dienstvertrag ORDER BY code`;
    return zeilen.map((z) => z.code);
  } catch {
    return [];
  }
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
  const [treffer, revisionen, regionen, determinismus, fdCodes] = await Promise.all([
    ladeTreffer(sql, lauf.quelleId, lauf.zeitraumArt),
    ladeRevisionen(sql, lauf.id),
    ladeRegionen(sql, lauf),
    ladeDeterminismus(sql, lauf),
    ladeFdCodes(sql),
  ]);
  const veroeffentlichen = await ladeVeroeffentlichen(sql, lauf, treffer);
  return {
    lauf,
    veroeffentlichen,
    vormonat,
    davor: nachbarn.has(davor),
    danach: nachbarn.has(danach),
    treffer,
    revisionen,
    regionen,
    determinismus,
    fdCodes,
  };
}

export function leseLaufDetail(lieferung: string, regelsatz = "v1"): Promise<Lesung<LaufDetail | null>> {
  return lies((sql) => ladeLaufDetail(sql, lieferung, regelsatz));
}
