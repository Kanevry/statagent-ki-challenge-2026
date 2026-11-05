import type { UcNavPunkt } from "@kic/ui/shell";

/**
 * Unter-Navigation von /uc1 (Pen-Frames KN6mU, B1gvr). Jeder Punkt ist eine Seite mit HTTP 200: das
 * Anti-Schablonen-Gate folgt jedem Link. Antrag, Stelle und Anliegen zeigen bis zum nächsten Stand einen Leerzustand.
 */
export const UC1_NAVIGATION: readonly UcNavPunkt[] = [
  { href: "/uc1", label: "Meine Situation" },
  { href: "/uc1/leistungen", label: "Erkannte Leistungen" },
  { href: "/uc1/antrag", label: "Antrag vorbereiten" },
  { href: "/uc1/stelle", label: "Stelle und Termin" },
  { href: "/uc1/anliegen", label: "Bisherige Anliegen" },
];
