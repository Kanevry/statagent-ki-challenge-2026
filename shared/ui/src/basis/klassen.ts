// Klassen zusammensetzen, leere Werte fallen weg. Bewusst ohne tailwind-merge: die Basis-Elemente
// setzen ihre Klassen selbst, `className` von außen ergänzt nur (Abstand, Breite).
export function klassen(...teile: Array<string | false | null | undefined>): string {
  return teile.filter(Boolean).join(" ");
}

// Sichtbarer Fokus für alle bedienbaren Elemente, in Klar-Grün.
export const fokus = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen";
