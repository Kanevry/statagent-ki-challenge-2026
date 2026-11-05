import { formatZahl } from "@kic/ui/bausteine";
import type { Regelsatz } from "@/components/uc3/navigation";

// Wer 407.604 erwartet, sieht zuerst 399.027 (Live-Test Lead 05.11.): Der Satz neben dem Schalter sagt, was jeder
// Regelsatz zählt, und nennt die Zahl des anderen für denselben Monat.

/** `andere`: Zahl des anderen Regelsatzes im selben Monat; null, wenn er diesen Monat nicht gerechnet hat. */
export function regelsatzSatz(aktiv: Regelsatz, andere: number | null): string {
  const zahl = andere === null ? "" : `: ${formatZahl(andere)}`;
  if (aktiv === "v1") return `Das ist Regelsatz v1, gezählt am Monatsletzten. Regelsatz v2 zählt das ganze Monat${zahl}.`;
  if (aktiv === "v2") return `Das ist Regelsatz v2, gezählt über das ganze Monat. Regelsatz v1 zählt am Monatsletzten${zahl}.`;
  // v3 und höher entstehen nur aus einer freigegebenen Änderung; verglichen wird dann mit v1 (page.tsx)
  return `Das ist Regelsatz ${aktiv}, mit einer freigegebenen Änderung. Regelsatz v1 zählt am Monatsletzten${zahl}.`;
}
