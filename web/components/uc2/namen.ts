// Namen und Wörter für die Oberfläche. Die Daten liefern Kennungen (`sv`, `kassenstellen`) und Zahlen (−2 bis +2);
// Bürger sollen Wörter lesen. Alles hier ist reine Anzeige und ändert keine Zahl.

/** Anzeigenamen der Akteure des Pools. Unbekannte Kennungen zeigen sich lesbar statt als Rohwert. */
export const AKTEUR_NAMEN: Record<string, string> = {
  aerztekammer: "Ärztekammer",
  finanzministerium: "Finanzministerium",
  gesetzgeber: "Gesetzgeber",
  gesundheitsministerium: "Gesundheitsministerium",
  krankenanstalten: "Spitäler",
  laender: "Länder",
  patienten: "Patientenvertretung",
  pflege: "Pflege",
  pharma: "Pharma",
  public_health: "Public Health",
  sozialpartner: "Sozialpartner",
  sv: "Sozialversicherung",
  vertragsaerzte: "Vertragsärzte",
  wahlaerzte: "Wahlärzte",
  moderator: "Moderator",
  experte: "Experte",
};

/** Ein Satz je Akteur, wer das ist. Steht in der Auswahl auf der Startseite. */
export const AKTEUR_KURZ: Record<string, string> = {
  aerztekammer: "Vertritt die Ärztinnen und Ärzte.",
  finanzministerium: "Achtet auf das Budget des Bundes.",
  gesetzgeber: "Beschließt die Gesetze.",
  gesundheitsministerium: "Verantwortet die Gesundheitspolitik.",
  krankenanstalten: "Betreiben die Spitäler und Ambulanzen.",
  laender: "Planen und bezahlen einen Teil der Spitäler.",
  patienten: "Spricht für die Patientinnen und Patienten.",
  pflege: "Vertritt die Pflegeberufe.",
  pharma: "Vertritt die Arzneimittelhersteller.",
  public_health: "Blickt auf die Gesundheit der Bevölkerung.",
  sozialpartner: "Arbeitgeber und Gewerkschaften.",
  sv: "Zahlt die Kassenleistungen.",
  vertragsaerzte: "Ärztinnen und Ärzte mit Kassenvertrag.",
  wahlaerzte: "Ärztinnen und Ärzte ohne Kassenvertrag.",
};

export function akteurName(id: string | null | undefined): string {
  if (!id) return "";
  return AKTEUR_NAMEN[id] ?? id.replaceAll("_", " ");
}

export interface ThemaText {
  /** Kurzer Name für Zeilen und Überschriften. */
  kurz: string;
  /** Eine Erklärung in Alltagssprache, die als Untertitel dient. */
  erklaerung: string;
}

/** Die Themen des Falls "wartezeiten". Für andere Fälle fällt die Anzeige auf den Titel aus dem Auftrag zurück. */
export const THEMEN: Record<string, ThemaText> = {
  kassenstellen: {
    kurz: "Kassenstellen",
    erklaerung: "Mehr Ärztinnen und Ärzte, die direkt mit der Krankenkasse abrechnen.",
  },
  triage: {
    kurz: "Digitale Vorauswahl",
    erklaerung: "Ein Online-Check klärt vorab, wer wie dringend zur Fachärztin oder zum Facharzt muss (Triage).",
  },
  finanzierung: {
    kurz: "Finanzierung",
    erklaerung: "Wer die Mehrkosten trägt: Bund, Länder oder die Krankenversicherung.",
  },
  patientenlenkung: {
    kurz: "Patientenlenkung",
    erklaerung: "Eine Hotline und die Hausarztpraxis schicken Patienten zum passenden Termin.",
  },
};

export function themaKurz(id: string, titel?: string): string {
  return THEMEN[id]?.kurz ?? titel ?? id.replaceAll("_", " ");
}

const HALTUNG_WORT: Record<number, string> = {
  [-2]: "klar dagegen",
  [-1]: "eher dagegen",
  0: "unentschieden",
  1: "eher dafür",
  2: "klar dafür",
};

export function haltungWort(haltung: number): string {
  return HALTUNG_WORT[haltung] ?? "unbekannt";
}

/** Haltung als Zahl mit Vorzeichen und echtem Minus: "+1", "−2", "0". */
export function haltungZahl(haltung: number): string {
  if (haltung > 0) return `+${haltung}`;
  if (haltung < 0) return `−${Math.abs(haltung)}`;
  return "0";
}

/**
 * Gedankenstriche gibt es auf der Seite nicht (Owner-Vorgabe). Texte aus dem Strom können welche enthalten:
 * Zwischen Ziffern wird daraus "bis", sonst ein Komma.
 */
export function ohneStriche(text: string): string {
  return text
    .replace(/(\d)\s*[–—]\s*(\d)/g, "$1 bis $2")
    .replace(/\s*[–—]\s*/g, ", ");
}

const ID_MUSTER = new RegExp(
  `\\b(${[...Object.keys(AKTEUR_NAMEN), ...Object.keys(THEMEN)].sort((a, b) => b.length - a.length).join("|")})\\b`,
  "g",
);

/**
 * Macht aus Modelltext Anzeigetext: Kennungen wie `sv` oder `kassenstellen` werden zu Namen, Striche verschwinden.
 * Zahlen und Satzbau bleiben unverändert.
 */
export function klartext(text: string): string {
  return ohneStriche(text).replace(ID_MUSTER, (id) => AKTEUR_NAMEN[id] ?? THEMEN[id]?.kurz ?? id);
}

/** Monat als "09/2026", Datum als "18.09.2026". Unbekanntes Format bleibt stehen. */
export function monatText(monat: string | null | undefined): string {
  const treffer = /^(\d{4})-(\d{2})/.exec(monat ?? "");
  return treffer ? `${treffer[2]}/${treffer[1]}` : (monat ?? "");
}

export function datumText(datum: string | null | undefined): string {
  const treffer = /^(\d{4})-(\d{2})-(\d{2})/.exec(datum ?? "");
  return treffer ? `${treffer[3]}.${treffer[2]}.${treffer[1]}` : (datum ?? "");
}

export const MAX_ZITAT = 300;

/** Zitat auf höchstens 300 Zeichen kürzen, an einer Wortgrenze, mit Auslassungspunkten. */
export function zitatText(zitat: string): string {
  const sauber = ohneStriche(zitat).replace(/\s+/g, " ").trim();
  if (sauber.length <= MAX_ZITAT) return sauber;
  const kurz = sauber.slice(0, MAX_ZITAT - 3);
  const wort = kurz.lastIndexOf(" ");
  return `${(wort > MAX_ZITAT / 2 ? kurz.slice(0, wort) : kurz).trimEnd()}...`;
}

export const KATEGORIE_WORT: Record<string, string> = {
  konsens: "Einigung",
  mehrheit: "Mehrheit dafür",
  abgelehnt: "Mehrheit dagegen",
  offener_konflikt: "Noch strittig",
};

export function kategorieWort(kategorie: string): string {
  return KATEGORIE_WORT[kategorie] ?? kategorie.replaceAll("_", " ");
}

/** Satz zum Ende der Verhandlung in Alltagssprache. */
export function abbruchSatz(runden: number, abbruch: string | null | undefined): string {
  const treffer = /^Runde (\d+) ohne Positionsänderung$/.exec(abbruch ?? "");
  if (treffer) return `Nach Runde ${treffer[1]} war Schluss, weil sich niemand mehr bewegt hat.`;
  if (!abbruch) return `Das Panel hat ${runden} Runden verhandelt.`;
  return `Das Panel hat ${runden} Runden verhandelt. Ende: ${klartext(abbruch)}`;
}
