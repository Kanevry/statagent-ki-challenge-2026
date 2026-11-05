import { absatzTexte, kopfzeile } from "../../../lib/praesentation/szenen-daten";
import { Fuss, k, Kreis, vars, type SzeneProps } from "./gemeinsam";

// Gestaltung: Kreise rollen nacheinander herein (Staffel 0,25 s), „+“ und „=“ kommen mit dem Kreis davor; die Reihe
// steht mittig (395 bis 1525). Zuletzt zeichnet sich der Mint-Ring um Kreis 3. Zeichen und Ziffern sind kein Inhalt.
const KREISE = [
  { n: 1, x: 395, t: 0.2 },
  { n: 2, x: 705, t: 0.45 },
  { n: 3, x: 1015, t: 0.7 },
] as const;
const ZEICHEN = [
  { z: "+", x: 595, t: 0.55 },
  { z: "+", x: 905, t: 0.8 },
  { z: "=", x: 1215, t: 1.05 },
] as const;

/** Szene 1: 1 + 2 + 3 = 4, darunter die Überschrift und die Zeile mit Name und Team. */
export function Gleichung({ folie }: SzeneProps) {
  const [klein] = absatzTexte(folie);
  return (
    <>
      {KREISE.map((c) => (
        <Kreis key={c.n} n={c.n} x={c.x} y={300} d={200} t={c.t} klasse={c.n === 3 ? "s1-roll ohne-ring" : "s1-roll"} />
      ))}
      <svg className={k("s1-ring")} viewBox="0 0 230 230" aria-hidden="true">
        <circle
          className={k("strich", "zeichnet")}
          style={vars({ t: 2.6, dauer: "1s" })}
          pathLength={1}
          cx={115}
          cy={115}
          r={113.5}
          transform="rotate(-90 115 115)"
        />
      </svg>
      {ZEICHEN.map((z, i) => (
        <p key={i} className={k("s1-op", "a")} style={{ left: z.x, ...vars({ t: z.t }) }} aria-hidden="true">
          {z.z}
        </p>
      ))}
      <Kreis n={4} x={1325} y={300} d={200} klasse="s1-k4" />
      <h1 className={k("s1-satz", "a")} style={vars({ t: 1.9 })}>
        {kopfzeile(folie)}
      </h1>
      {klein && (
        <p className={k("s1-klein", "a")} style={vars({ t: 2.2 })}>
          {klein}
        </p>
      )}
      <Fuss folie={folie} />
    </>
  );
}
