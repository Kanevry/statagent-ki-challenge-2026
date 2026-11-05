import { absatzTexte, kopfzeile, zahlWert } from "../../../lib/praesentation/szenen-daten";
import { Fuss, k, Raster, vars, Zaehler, type SzeneProps } from "./gemeinsam";

// Gestaltung: 96 Spalten, wie im Prototyp (2.880 Zellen ergeben 30 Zeilen).
const SPALTEN = 96;

/** Szene 5: Raster mit so vielen Zellen wie die Zahl aus `zahl`, die Zahl zählt hoch, daneben „von …“. */
export function BelegSzene({ folie, nr, aktiv }: SzeneProps) {
  const zahl = folie.daten.zahl ?? kopfzeile(folie);
  const stelle = zahl.indexOf(" von ");
  const gross = stelle === -1 ? zahl : zahl.slice(0, stelle);
  const von = stelle === -1 ? "" : zahl.slice(stelle + 1);
  const ziel = zahlWert(gross);
  const [satz, bruecke] = absatzTexte(folie);
  return (
    <>
      {Number.isFinite(ziel) && ziel > 0 && <Raster anzahl={ziel} spalten={SPALTEN} aktiv={aktiv} />}
      <p className={k("s5-zahl")} aria-label={zahl}>
        <Zaehler ziel={ziel} aktiv={aktiv} className={k("s5-gross")} />
        {von && <span className={k("s5-von")}>{von}</span>}
      </p>
      {satz && (
        <p className={k("s5-satz", "a")} style={vars({ i: 4 })}>
          {satz}
        </p>
      )}
      {bruecke && (
        <p className={k("s5-bruecke", "a")} style={vars({ i: 6 })}>
          {bruecke}
        </p>
      )}
      <Fuss folie={folie} nr={nr} />
    </>
  );
}
