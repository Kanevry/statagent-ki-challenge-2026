import { absatzTexte, kopfzeile, tabelle, zahlWert } from "../../../lib/praesentation/szenen-daten";
import { Fuss, Haken, k, Kreis, vars, type SzeneProps } from "./gemeinsam";

// Gestaltung: Kalenderleiste mit zwölf Feldern, ein dreizehntes schiebt sich dazu.
const MONATE = Array.from({ length: 13 }, (_, i) => i + 1);
const BALKEN_T = [2.3, 2.5] as const;

/**
 * Szene 7: Kalenderleiste mit 13. Monat (gelb), daneben der erste Absatz. Je Tabellenzeile ein Balken, Länge = Wert
 * durch die Gesamtzahl aus dem Spaltenkopf („… von 576“). Eine Zeile mit 0 bekommt statt Balken den Mint-Haken und
 * den Text aus `treffer`. Darunter der Schlusssatz, unten die Herkunft.
 */
export function Annahme({ folie, nr }: SzeneProps) {
  const t = tabelle(folie);
  const kopf = t?.kopf[1] ?? "";
  const gesamt = zahlWert(/von\s+([\d.]+)/.exec(kopf)?.[1]);
  const treffer = folie.daten.treffer;
  const [anzahl, satz] = absatzTexte(folie);
  return (
    <>
      <Kreis n={3} x={120} y={92} d={72} t={0} />
      <h2 className={k("titel", "a")} style={vars({ t: 0.1 })}>
        {kopfzeile(folie)}
      </h2>
      <ol className={k("s7-kalender")} aria-hidden="true">
        {MONATE.map((m) => (
          <li key={m} className={k("s7-feld", m === 13 && "s7-dreizehn")} style={vars({ i: m - 1 })}>
            <span className={k("s7-innen")}>{m}</span>
          </li>
        ))}
      </ol>
      {anzahl && (
        <p className={k("s7-anzahl", "a")} style={vars({ t: 1.9 })}>
          {anzahl}
        </p>
      )}
      <p className={k("s7-balkentitel", "a")} style={vars({ t: 2.1 })}>
        {kopf}
      </p>
      <ol className={k("s7-balken")} aria-label={kopf}>
        {(t?.zeilen ?? []).map(([name = "", wert = ""], i) => {
          const v = zahlWert(wert);
          const anteil = Number.isFinite(gesamt) && gesamt > 0 ? Math.min(1, v / gesamt) : 0;
          const bt = BALKEN_T[i] ?? 2.3 + i * 0.2;
          return (
            <li key={i} className={k("s7-zeile")}>
              <p className={k("s7-name")}>{name}</p>
              <div className={k("s7-spur")}>
                {v === 0 ? (
                  <>
                    <span className={k("s7-zahl", "a")} style={vars({ t: 2.75 })}>
                      {wert}
                    </span>
                    <Haken klasse="s7-haken" viewBox="0 0 48 42" d="M7 22l11 11L42 8" t={3} />
                    {treffer && (
                      <span className={k("s7-trifft", "a")} style={vars({ t: 3.3 })}>
                        {treffer}
                      </span>
                    )}
                  </>
                ) : (
                  <>
                    <span className={k("s7-wert")} style={vars({ v: anteil.toFixed(4), t: bt })} />
                    <span className={k("s7-zahl", "a")} style={vars({ t: bt + 0.5 })}>
                      {wert}
                    </span>
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      {satz && (
        <p className={k("s7-satz", "a")} style={vars({ t: 3.6 })}>
          {satz}
        </p>
      )}
      <Fuss folie={folie} nr={nr} />
    </>
  );
}
