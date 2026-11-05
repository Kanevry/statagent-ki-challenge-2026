import { absatzTexte, kopfzeile } from "../../../lib/praesentation/szenen-daten";
import { Fuss, k, Kreis, vars, type SzeneProps } from "./gemeinsam";

// Gestaltung: Lage und Auftritt (Sekunden) der vier Absätze unter der Überschrift.
const ABSAETZE = [
  { klasse: "s10-satz s10-zwei", t: 0.8 },
  { klasse: "s10-live", t: 1.3 },
  { klasse: "s10-offline", t: 1.7 },
  { klasse: "s10-klein", t: 2.1 },
] as const;

/**
 * Szene 10: Überschrift und erster Absatz oben, in der Mitte der Mint-Kreis 4 (gleitet aus Szene 9 herüber, atmet
 * zweimal), darunter der zweite Absatz groß in Mint, der dritte als Nebentext, der vierte unten. Kein Knopf.
 */
export function Schluss({ folie }: SzeneProps) {
  const absaetze = absatzTexte(folie);
  return (
    <>
      <h2 className={k("s10-satz", "s10-eins", "a")} style={vars({ t: 0.4 })}>
        {kopfzeile(folie)}
      </h2>
      <Kreis n={4} x={850} y={330} d={220} klasse="s10-k4" />
      {ABSAETZE.map((a, i) =>
        absaetze[i] ? (
          <p key={i} className={k(...a.klasse.split(" "), "a")} style={vars({ t: a.t })}>
            {absaetze[i]}
          </p>
        ) : null,
      )}
      <Fuss folie={folie} />
    </>
  );
}
