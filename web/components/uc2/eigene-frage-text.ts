// Gliedert den Antworttext von UC2 (`uc2.antwort`) für die Anzeige. Der Text bleibt, wie er ist: Zeilen, die nicht passen,
// stehen unverändert unter `rest`, damit bei geändertem Format nichts verschwindet.

export interface Stimme {
  name: string;
  haltung: string;
  grund: string;
  beleg: string | null;
}

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

const STIMME = /^- (Patient:innenvertretung|[^:]+): (.*)$/;
/** Quelle am Ende der Zeile; „Beispielbeleg, erfunden“ steht online nur ohne Presse-Index und bleibt so gekennzeichnet. */
const QUELLE = / (Beleg|Beispielbeleg, erfunden): ([^:]*)$/;

function stimmeAus(name: string, inhalt: string): Stimme {
  const grundBei = inhalt.indexOf("Grund: ");
  const haltung = grundBei >= 0 ? inhalt.slice(0, grundBei).trim() : "";
  const nachHaltung = grundBei >= 0 ? inhalt.slice(grundBei + 7) : inhalt;
  const quelle = QUELLE.exec(nachHaltung);
  return {
    name,
    haltung,
    grund: (quelle ? nachHaltung.slice(0, quelle.index) : nachHaltung).trim(),
    beleg: quelle ? `${quelle[1] === "Beleg" ? "" : "Beispiel, erfunden: "}${quelle[2]!.replace(/\.$/, "")}` : null,
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
  for (const zeile of text.split("\n").map((z) => z.trim()).filter(Boolean)) {
    const stimme = STIMME.exec(zeile);
    if (stimme) ergebnis.stimmen.push(stimmeAus(stimme[1]!, stimme[2]!));
    else if (zeile.startsWith(THEMEN)) ergebnis.themen = themenAus(zeile.slice(THEMEN.length));
    else if (zeile.startsWith("Kurz gesagt: ")) continue; // sagt dasselbe wie die Themenzeile, nur länger
    else if (zeile.startsWith("Bedingungen: ")) ergebnis.bedingungen = zeile.slice(13).split("; ").map((b) => b.trim().replace(/\.+$/, ".")).filter(Boolean);
    else if (zeile !== "Wer ist dafür, wer dagegen:") ergebnis.rest.push(zeile);
  }
  return ergebnis;
}
