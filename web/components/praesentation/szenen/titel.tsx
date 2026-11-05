import { absatzTexte, kopfzeile, saetze } from "../../../lib/praesentation/szenen-daten";
import { Fuss, k, vars, type SzeneProps } from "./gemeinsam";

/** Szene 1: Marke, drei Sätze nacheinander, das Wort aus `hervorheben` wird zuletzt Mint. */
export function Titel({ folie, nr }: SzeneProps) {
  const [satzzeile = "", ...rest] = absatzTexte(folie);
  const wort = folie.daten.hervorheben;
  return (
    <>
      <h1 className={k("s1-marke", "a")} style={vars({ i: 0 })}>
        {kopfzeile(folie)}
      </h1>
      <ul className={k("s1-saetze")}>
        {saetze(satzzeile).map((satz, i) => {
          const stelle = wort ? satz.indexOf(wort) : -1;
          return (
            <li key={i} className={k("a")} style={vars({ i })}>
              {stelle === -1 || !wort ? (
                satz
              ) : (
                <>
                  {satz.slice(0, stelle)}
                  <span className={k("s1-mensch")}>{wort}</span>
                  {satz.slice(stelle + wort.length)}
                </>
              )}
            </li>
          );
        })}
      </ul>
      {rest.map((zeile, i) => (
        <p key={i} className={k("s1-zeile", "a")} style={vars({ i: 20 + i })}>
          {zeile}
        </p>
      ))}
      <Fuss folie={folie} nr={nr} />
    </>
  );
}
