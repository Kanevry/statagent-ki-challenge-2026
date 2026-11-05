import { inlineText } from "../../../lib/praesentation/markdown";
import { absatzTexte, kopfzeile, listenPunkte, tabelle } from "../../../lib/praesentation/szenen-daten";
import { Fuss, k, Kopf, vars, type SzeneProps } from "./gemeinsam";

/**
 * Szene „zahlen“ (ohne Takte): Titel als ganzer Satz, darunter bis zu drei große Zahlen aus der Tabelle (Spalten
 * Zahl und Text), oder eine Liste von Sätzen. Der erste Absatz steht klein darunter. Für die Management-Fassung.
 */
export function ZahlenSzene({ folie }: SzeneProps) {
  const zeilen = tabelle(folie)?.zeilen ?? [];
  const saetze = listenPunkte(folie).map(inlineText);
  const [satz] = absatzTexte(folie);
  return (
    <>
      <Kopf titel={kopfzeile(folie)} />
      {zeilen.length > 0 && (
        <ul className={k("z-zahlen")}>
          {zeilen.slice(0, 3).map(([zahl = "", text = ""], i) => (
            <li key={i} className={k("z-kachel", "a")} style={vars({ t: 0.3 + i * 0.25 })}>
              <p className={k("z-zahl")}>{zahl}</p>
              <p className={k("z-text")}>{text}</p>
            </li>
          ))}
        </ul>
      )}
      {saetze.length > 0 && (
        <ol className={k("z-saetze")}>
          {saetze.slice(0, 4).map((s, i) => (
            <li key={i} className={k("z-satz", "a")} style={vars({ t: 0.3 + i * 0.25 })}>
              {s}
            </li>
          ))}
        </ol>
      )}
      {satz && (
        <p className={k("z-fuss", "a")} style={vars({ t: 1.2 })}>
          {satz}
        </p>
      )}
      <Fuss folie={folie} />
    </>
  );
}
