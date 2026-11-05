import { absatzTexte, kopfzeile } from "../../../lib/praesentation/szenen-daten";
import { Fuss, k, Kreis, vars, type SzeneProps } from "./gemeinsam";

// Gestaltung: drei Kreise rollen herein (3 zuerst), dann „=“ und der Kreis 4 wächst. Zeichen sind kein Inhalt.
const KREISE = [
  { n: 1, x: 340, t: 0.56 },
  { n: 2, x: 650, t: 0.38 },
  { n: 3, x: 960, t: 0.2 },
] as const;
const ZEICHEN = [
  { z: "+", x: 540, t: 1.5 },
  { z: "+", x: 850, t: 1.65 },
  { z: "=", x: 1160, t: 1.85 },
] as const;

/** Szene 1: 1 + 2 + 3 = 4, darunter die Überschrift und die Zeile mit Name und Team. */
export function Gleichung({ folie, nr }: SzeneProps) {
  const [klein] = absatzTexte(folie);
  return (
    <>
      {KREISE.map((c) => (
        <Kreis key={c.n} n={c.n} x={c.x} y={300} d={200} t={c.t} klasse="s1-roll" />
      ))}
      {ZEICHEN.map((z, i) => (
        <p key={i} className={k("s1-op", "a")} style={{ left: z.x, ...vars({ t: z.t }) }} aria-hidden="true">
          {z.z}
        </p>
      ))}
      <Kreis n={4} x={1270} y={300} d={200} klasse="s1-k4" />
      <h1 className={k("s1-satz", "a")} style={vars({ t: 2.85 })}>
        {kopfzeile(folie)}
      </h1>
      {klein && (
        <p className={k("s1-klein", "a")} style={vars({ t: 3.25 })}>
          {klein}
        </p>
      )}
      <Fuss folie={folie} nr={nr} />
    </>
  );
}
