import { formatZahl } from "@kic/ui/bausteine";

// Wer 407.604 erwartet, sieht zuerst 399.027 (Live-Test Lead 05.11.): Der Satz neben dem Schalter sagt, was jeder
// Regelsatz zählt, und nennt die Zahl des anderen für denselben Monat.

/** `andere`: Zahl des anderen Regelsatzes im selben Monat; null, wenn er diesen Monat nicht gerechnet hat. */
export function regelsatzSatz(aktiv: "v1" | "v2", andere: number | null): string {
  const zahl = andere === null ? "" : `: ${formatZahl(andere)}`;
  return aktiv === "v1"
    ? `Das ist Regelsatz v1, gezählt am Monatsletzten. Regelsatz v2 zählt das ganze Monat${zahl}.`
    : `Das ist Regelsatz v2, gezählt über das ganze Monat. Regelsatz v1 zählt am Monatsletzten${zahl}.`;
}
