import { absatzTexte, kopfzeile } from "../../../lib/praesentation/szenen-daten";
import { Fuss, k, vars, type SzeneProps } from "./gemeinsam";

/** Szene 11: zwei Sätze (Überschrift, dann erster Absatz in Mint), darunter klein die Fundstellen. */
export function Schluss({ folie, nr }: SzeneProps) {
  const [zwei, klein] = absatzTexte(folie);
  return (
    <>
      <h2 className={k("s11-satz", "s11-eins", "a")} style={vars({ i: 0 })}>
        {kopfzeile(folie)}
      </h2>
      {zwei && (
        <p className={k("s11-satz", "s11-zwei", "a")} style={vars({ i: 0 })}>
          {zwei}
        </p>
      )}
      {klein && (
        <p className={k("s11-klein", "a")} style={vars({ i: 18 })}>
          {klein}
        </p>
      )}
      <Fuss folie={folie} nr={nr} />
    </>
  );
}
