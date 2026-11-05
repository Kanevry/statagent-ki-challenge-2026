import { absatzTexte, kopfzeile, tabelle } from "../../../lib/praesentation/szenen-daten";
import { Blick, Fuss, k, Kreis, vars, type SzeneProps } from "./gemeinsam";

/**
 * Hintergrund-Strom: Datumsmuster ohne Bedeutung und ohne IDs, deterministisch (gleicher Seed, gleiches Bild).
 * Reine Gestaltung, für Screenreader verborgen.
 */
function stromBahnen(): string[] {
  let seed = 7;
  const zufall = (n: number) => {
    seed = (seed * 9301 + 49297) % 233280;
    return Math.floor((seed / 233280) * n);
  };
  const zwei = (n: number) => String(n).padStart(2, "0");
  return [0, 1, 2, 3].map(() =>
    Array.from({ length: 9 }, () => `${1940 + zufall(66)}-${zwei(1 + zufall(12))}-${zwei(1 + zufall(28))}  ${2024 + zufall(2)}-${zwei(1 + zufall(12))}`).join("     "),
  );
}
const BAHNEN = stromBahnen();
const BAHN_Y = [62, 186, 310, 372];

/**
 * Szene 6: Ein ruhiger Strom aus Datenzeilen läuft durch, drei Zeilen der Tabelle bleiben hängen, werden gelb und
 * wachsen zu großen Zeilen (Muster, Falle, Umfang). Darunter der Absatz, unten die Herkunft. Kreis 3 neben dem Titel.
 */
export function Fallen({ folie, nr }: SzeneProps) {
  const zeilen = tabelle(folie)?.zeilen ?? [];
  const [dazu] = absatzTexte(folie);
  return (
    <>
      <Kreis n={3} x={120} y={92} d={72} t={0} />
      <h2 className={k("titel", "a")} style={vars({ t: 0.1 })}>
        {kopfzeile(folie)}
      </h2>
      <div className={k("s6-strom")} aria-hidden="true">
        {BAHNEN.map((text, b) => (
          <p key={b} className={k("s6-bahn")} style={{ top: BAHN_Y[b], ...vars({ t: (b * 0.12).toFixed(2) }) }}>
            {text}
          </p>
        ))}
      </div>
      <ol className={k("s6-fallen")}>
        {zeilen.slice(0, 3).map(([muster = "", was = "", umfang = ""], i) => (
          <li key={i} className={k("s6-falle")} style={{ top: i * 124, ...vars({ t: 0.25 + i * 0.15 }) }}>
            <span className={k("s6-code")} aria-hidden="true">
              {muster}
            </span>
            <p className={k("s6-was")}>{was}</p>
            <p className={k("s6-zahl")}>{umfang}</p>
          </li>
        ))}
      </ol>
      {dazu && (
        <p className={k("s6-dazu", "a")} style={vars({ t: 3 })}>
          {dazu}
        </p>
      )}
      <Blick folie={folie} breite={620} t={3.4} />
      <Fuss folie={folie} nr={nr} />
    </>
  );
}
