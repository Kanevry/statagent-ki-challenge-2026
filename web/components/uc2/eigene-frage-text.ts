// Gliedert den Antworttext von UC2 (`uc2.antwort`) für die Anzeige. Der Text bleibt, wie er ist: Zeilen, die nicht passen,
// stehen unverändert unter `rest`, damit bei geändertem Format nichts verschwindet.

export interface Stimme {
  name: string;
  haltung: string;
  grund: string;
  beleg: string | null;
  ohneArtikel: boolean;
}

/** Steht bei einer Haltung ohne Zeitungsartikel unter dem Grund. */
export const OHNE_ARTIKEL = "Kein Zeitungsartikel dazu. Die Haltung folgt nur aus der Beschreibung der Rolle.";

export interface ThemaStand {
  thema: string;
  stand: string;
}

export interface Gegliedert {
  themen: ThemaStand[];
  stimmen: Stimme[];
  bedingungen: string[];
  rest: string[];
}

const STIMME = /^- ([^:]+): (.*)$/;
/** Quelle am Ende der Zeile; „Beispielbeleg, erfunden“ steht online nur ohne Presse-Index und bleibt so gekennzeichnet. */
const QUELLE = / (Beleg|Beispielbeleg, erfunden): ([^:]*)$/;
/** Dieser Zusatz des Codes hält die fehlende Quelle fest; die Seite sagt es mit `OHNE_ARTIKEL` in Alltagsworten. */
const OHNE_QUELLE = / Modellannahme: Dazu gibt es keinen Zeitungsartikel\..*$/;
/** Werkstattwörter gehören nicht in die Stimme einer Organisation. Der Prompt verbietet sie; was durchrutscht, fällt hier weg. */
const WERKSTATT = /modellannahme|beispielbeleg|\bbeleg(?:e|en|es|s|t|te|ten)?\b/i;

/** Lässt nur Sätze ohne Werkstattwort stehen. */
function ohneWerkstatt(text: string): string {
  return text
    .split(/(?<=[.!?])\s+/)
    .filter((satz) => !WERKSTATT.test(satz))
    .join(" ")
    .trim();
}

function stimmeAus(name: string, inhalt: string): Stimme {
  const grundBei = inhalt.indexOf("Grund: ");
  const haltung = grundBei >= 0 ? inhalt.slice(0, grundBei).trim() : "";
  const nachHaltung = grundBei >= 0 ? inhalt.slice(grundBei + 7) : inhalt;
  const quelle = QUELLE.exec(nachHaltung);
  const ohneQuelle = OHNE_QUELLE.exec(nachHaltung);
  const grundEnde = quelle?.index ?? ohneQuelle?.index ?? nachHaltung.length;
  return {
    name,
    haltung,
    grund: ohneWerkstatt(nachHaltung.slice(0, grundEnde)),
    beleg: quelle ? `${quelle[1] === "Beleg" ? "" : "Beispiel, erfunden: "}${quelle[2]!.replace(/\.$/, "")}` : null,
    ohneArtikel: ohneQuelle !== null,
  };
}

const THEMEN = "So stehen die Beteiligten zu den Themen: ";

function themenAus(text: string): ThemaStand[] {
  return text
    .replace(/\.$/, "")
    .split("; ")
    .flatMap((teil) => {
      const trenner = teil.lastIndexOf(": ");
      return trenner > 0 ? [{ thema: teil.slice(0, trenner), stand: teil.slice(trenner + 2) }] : [];
    });
}

export function gliedere(text: string): Gegliedert {
  const ergebnis: Gegliedert = { themen: [], stimmen: [], bedingungen: [], rest: [] };
  const einheitlich = text.replaceAll("Patient:innenvertretung", "Patientenvertretung"); // Wort wie auf /uc2
  for (const zeile of einheitlich.split("\n").map((z) => z.trim()).filter(Boolean)) {
    const stimme = STIMME.exec(zeile);
    if (stimme) ergebnis.stimmen.push(stimmeAus(stimme[1]!, stimme[2]!));
    else if (zeile.startsWith(THEMEN)) ergebnis.themen = themenAus(zeile.slice(THEMEN.length));
    else if (zeile.startsWith("Kurz gesagt: ")) continue; // sagt dasselbe wie die Themenzeile, nur länger
    else if (zeile.startsWith("Bedingungen: ")) ergebnis.bedingungen = zeile.slice(13).split("; ").map((b) => b.trim().replace(/\.+$/, ".")).filter((b) => b && !WERKSTATT.test(b));
    else if (zeile !== "Wer ist dafür, wer dagegen:") ergebnis.rest.push(zeile);
  }
  return ergebnis;
}
