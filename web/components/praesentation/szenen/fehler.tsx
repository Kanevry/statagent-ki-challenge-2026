import { absatzTexte, kopfzeile, tabelle } from "../../../lib/praesentation/szenen-daten";
import { an, Fuss, k, Kopf, taktAn, vars, type SzeneProps } from "./gemeinsam";

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
 * Szene 6 (drei Takte): Beim Betreten läuft ein ruhiger Strom aus Datenzeilen durch. Je Takt bleibt eine Zeile der
 * Tabelle hängen (Muster, Fehler, Anzahl, Lieferung), wird gelb und groß. Im dritten Takt der Absatz darunter.
 */
export function Fehler({ folie, takt }: SzeneProps) {
  const zeilen = tabelle(folie)?.zeilen ?? [];
  const [dazu] = absatzTexte(folie);
  return (
    <>
      <Kopf titel={kopfzeile(folie)} />
      <div className={k("s6-strom")} aria-hidden="true">
        {BAHNEN.map((text, b) => (
          <p key={b} className={k("s6-bahn")} style={{ top: BAHN_Y[b], ...vars({ t: (b * 0.12).toFixed(2) }) }}>
            {text}
          </p>
        ))}
      </div>
      <ol className={k("s6-fallen")}>
        {zeilen.slice(0, 3).map(([muster = "", was = "", anzahl = "", lieferung = ""], i) => (
          <li key={i} className={k("s6-falle", an(i + 1, takt))} {...taktAn(i + 1)} style={{ top: i * 124 }}>
            <span className={k("s6-code")} aria-hidden="true">
              {muster}
            </span>
            <p className={k("s6-was")}>{was}</p>
            <p className={k("s6-zahl")}>{anzahl}</p>
            <p className={k("s6-monat")}>{lieferung}</p>
          </li>
        ))}
      </ol>
      {dazu && (
        <p className={k("s6-dazu", an(3, takt))} {...taktAn(3)} style={vars({ tt: 1.8 })}>
          {dazu}
        </p>
      )}
      <Fuss folie={folie} />
    </>
  );
}
