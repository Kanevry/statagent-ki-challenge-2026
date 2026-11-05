import { inlineText } from "../../../lib/praesentation/markdown";
import { absatzTexte, kopfUndRest, listenPunkte, tabelle } from "../../../lib/praesentation/szenen-daten";
import { Fuss, Getippt, k, vars, type SzeneProps } from "./gemeinsam";

/**
 * Szene 10: die Frage tippt sich ein, ein Pfad durch die drei Stationen der Liste, darunter klein die Tabelle
 * (nächster Schritt und Nutzen je Use Case, AC aus #89) und der gemeinsame Kern. Das Kürzel (UC3) steht inline in
 * der Überschrift, damit es kein Etikett über ihr wird.
 */
export function Einstieg({ folie, nr, aktiv }: SzeneProps) {
  const [frage = "", kern] = absatzTexte(folie);
  const stationen = listenPunkte(folie).map(kopfUndRest);
  const t = tabelle(folie);
  return (
    <>
      <p className={k("s10-frage")} aria-label={frage}>
        <Getippt text={frage} aktiv={aktiv} />
      </p>
      <div className={k("s10-weg")}>
        <div className={k("s10-linie")} />
        <ol className={k("s10-stationen")}>
          {stationen.map((s, i) => {
            const kopf = inlineText(s.kopf);
            const leer = kopf.indexOf(" ");
            const code = leer === -1 ? "" : kopf.slice(0, leer);
            return (
              <li key={i} className={k("s10-station")} style={vars({ i })}>
                <h2>
                  {code && <span className={k("s10-code")}>{code}</span>}
                  {leer === -1 ? kopf : kopf.slice(leer + 1)}
                </h2>
                <p>{s.rest}</p>
              </li>
            );
          })}
        </ol>
      </div>
      {t && (
        <table className={k("s10-schritte")}>
          <thead>
            <tr>
              {t.kopf.map((z, i) => (
                <th key={i} scope="col">
                  {z}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {t.zeilen.map((zeile, i) => (
              <tr key={i}>
                {zeile.map((z, j) => (
                  <td key={j}>{z}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {kern && <p className={k("s10-kern")}>{kern}</p>}
      <Fuss folie={folie} nr={nr} />
    </>
  );
}
