/**
 * Farben der dunklen Bühne (nur auf /praesentation, Owner-Entscheid). Die Werte stammen aus dem Pen-Frame H8TJkE.
 * Dafür gibt es in `shared/ui/src/tokens.css` noch kein Token; alle drei stehen nur hier, damit sie sich später
 * an einer Stelle durch Token-Klassen ersetzen lassen. Alles andere kommt aus den Tokens (text-paper, text-gelb,
 * font-display, font-sans, font-mono).
 */
export const BUEHNE = {
  /** Grund der Bühne (Pen: #060F15) */
  grund: "bg-[#060f15]",
  /** Haarlinien auf der Bühne (Pen: #1E3542) */
  linie: "border-[#1e3542]",
  /** Nebentext auf der Bühne (Pen: #8FA3AD) */
  gedaempft: "text-[#8fa3ad]",
} as const;

/** Feste Größe der Bühne; die Schau skaliert sie auf das Fenster. */
export const BUEHNE_BREITE = 1920;
export const BUEHNE_HOEHE = 1080;
