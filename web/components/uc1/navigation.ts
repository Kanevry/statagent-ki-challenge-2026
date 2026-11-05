import type { UcNavPunkt } from "@kic/ui/shell";

/**
 * Unter-Navigation von /uc1 (Pen-Frames KN6mU, B1gvr), mit denselben Wörtern wie der Schrittzeiger. Jeder Punkt ist eine Seite mit HTTP 200: das
 * Anti-Schablonen-Gate folgt jedem Link. Ohne Antwort zeigen die Unterseiten einen ehrlichen Leerzustand.
 */
export const UC1_NAVIGATION: readonly UcNavPunkt[] = [
  { href: "/uc1", label: "Situation" },
  { href: "/uc1/leistungen", label: "Leistungen" },
  { href: "/uc1/antrag", label: "Antrag" },
  { href: "/uc1/stelle", label: "Stelle" },
  { href: "/uc1/anliegen", label: "Anliegen" },
];
