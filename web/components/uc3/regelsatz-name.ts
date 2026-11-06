import { formatZahl } from "@kic/ui/bausteine";

// Wörter für die Fassungen der Regeln (Wortliste der Polish-Runde). In der Adresse und in der Datenbank bleiben v1 und
// v2; sichtbar steht nur, was jemand ohne Vorwissen versteht. Die Aufgabe verlangt beide Stände: „nach den alten Regeln
// und nach den Änderungsaufträgen“.

const nummer = (regelsatz: string): string | null => /^v(\d+)$/.exec(regelsatz)?.[1] ?? null;

/** Name für Schalter, Spalten und Kopfzeilen: „Alte Regeln“, „Nach den Änderungsaufträgen“. */
export function regelsatzName(regelsatz: string): string {
  if (regelsatz === "v1") return "Alte Regeln";
  if (regelsatz === "v2") return "Nach den Änderungsaufträgen";
  if (regelsatz === "ministerium") return "Ministeriums-Lieferung";
  const n = nummer(regelsatz);
  return n ? `Neue Fassung ${n}` : regelsatz;
}

/** Für den Satz: „nach den alten Regeln gerechnet“. */
export function mitRegeln(regelsatz: string): string {
  if (regelsatz === "v1") return "nach den alten Regeln";
  if (regelsatz === "v2") return "nach den Änderungsaufträgen";
  if (regelsatz === "ministerium") return "für die Ministeriums-Lieferung";
  const n = nummer(regelsatz);
  return n ? `nach der neuen Fassung ${n}` : `nach ${regelsatz}`;
}

/** Für den Satz: „ändert eine Regel im Stand nach den Änderungsaufträgen“. */
export function imStand(regelsatz: string): string {
  if (regelsatz === "v1") return "in den alten Regeln";
  if (regelsatz === "v2") return "im Stand nach den Änderungsaufträgen";
  if (regelsatz === "ministerium") return "für die Ministeriums-Lieferung";
  const n = nummer(regelsatz);
  return n ? `in der neuen Fassung ${n}` : `in ${regelsatz}`;
}

/** Erster Buchstabe groß, für den Satzanfang. */
export function satzAnfang(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * Satz neben dem Schalter: was hier zählt, und die Zahl des anderen Stands für denselben Monat.
 * `andere`: Zahl des anderen Stands; null, wenn er diesen Monat nicht gerechnet hat oder es um keinen Monat geht.
 */
export function regelsatzSatz(aktiv: string, andere: number | null): string {
  const zahl = andere === null ? null : formatZahl(andere);
  if (aktiv === "v1") {
    return `Sie sehen die alten Regeln: Gezählt wird am Stichtag, dem letzten Tag des Monats. Nach den Änderungsaufträgen zählt der ganze Monat${zahl ? `: ${zahl}` : ""}.`;
  }
  if (aktiv === "v2") {
    return `Sie sehen den Stand nach den Änderungsaufträgen: Gezählt wird über den ganzen Monat. ${
      zahl ? `Nach den alten Regeln, gezählt am Stichtag, sind es ${zahl}.` : "Nach den alten Regeln zählt der Stichtag."
    }`;
  }
  // v3 und höher entstehen erst aus einer freigegebenen Live-Änderung; was die zählen, sagt erst die Regel.
  return `Sie sehen eine neue Fassung mit einer frisch freigegebenen Änderung. ${
    zahl ? `Nach den alten Regeln sind es ${zahl}.` : "Die alten Regeln bleiben daneben bestehen."
  }`;
}
