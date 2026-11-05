import Link from "next/link";
import { liveKomponente } from "../../../lib/praesentation/live";
import { absatzTexte, kopfzeile } from "../../../lib/praesentation/szenen-daten";
import { Fuss, k, Kreis, vars, type SzeneProps } from "./gemeinsam";

/**
 * Szene 9: zwei Sätze (Überschrift, erster Absatz), der Mint-Kreis 4 atmet zweimal, darunter der Knopf `knopf`
 * zur Route `route` (nur Routen aus der Registry in lib/praesentation/live.tsx) und die kleine Zeile.
 */
export function Schluss({ folie, nr }: SzeneProps) {
  const [zwei, klein] = absatzTexte(folie);
  const { route, knopf } = folie.daten;
  const erlaubt = liveKomponente(route) !== undefined;
  return (
    <>
      <h2 className={k("s9-satz", "s9-eins", "a")} style={vars({ t: 0.6 })}>
        {kopfzeile(folie)}
      </h2>
      {zwei && (
        <p className={k("s9-satz", "s9-zwei", "a")} style={vars({ t: 1.1 })}>
          {zwei}
        </p>
      )}
      <Kreis n={4} x={830} y={388} d={260} klasse="s9-k4" />
      {erlaubt && route && knopf && (
        <Link href={route} className={k("s9-knopf")} data-live-route={route}>
          {knopf}
        </Link>
      )}
      {klein && (
        <p className={k("s9-klein", "a")} style={vars({ t: 1.9 })}>
          {klein}
        </p>
      )}
      <Fuss folie={folie} nr={nr} />
    </>
  );
}
