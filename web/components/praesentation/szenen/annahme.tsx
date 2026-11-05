import { absatzTexte, kopfzeile, tabelle, zahlWert } from "../../../lib/praesentation/szenen-daten";
import { an, Fuss, Haken, k, Kopf, taktAn, vars, type SzeneProps } from "./gemeinsam";

// Gestaltung: Kalenderleiste mit zwölf Feldern, ein dreizehntes schiebt sich dazu.
const MONATE = Array.from({ length: 13 }, (_, i) => i + 1);

/**
 * Szene 8 (drei Takte): 1 Kalenderleiste mit 13. Monat und der erste Absatz groß in Gelb; 2 die Tabelle als Balken,
 * Länge = Wert durch die erste Zahl im Spaltenkopf (576), eine Zeile mit 0 bekommt den Haken und `treffer`;
 * 3 der Schlusssatz.
 */
export function Annahme({ folie, takt }: SzeneProps) {
  const t = tabelle(folie);
  const kopf = t?.kopf[1] ?? "";
  const gesamt = zahlWert(kopf);
  const treffer = folie.daten.treffer;
  const [anzahl, satz] = absatzTexte(folie);
  return (
    <>
      <Kopf titel={kopfzeile(folie)} />
      <ol className={k("s8-kalender", an(1, takt))} {...taktAn(1)} aria-hidden="true">
        {MONATE.map((m) => (
          <li key={m} className={k("s8-feld", m === 13 && "s8-dreizehn")} style={vars({ i: m - 1 })}>
            <span className={k("s8-innen")}>{m}</span>
          </li>
        ))}
      </ol>
      {anzahl && (
        <p className={k("s8-gross", an(1, takt))} {...taktAn(1)} style={vars({ tt: 1.8 })}>
          {anzahl}
        </p>
      )}
      <p className={k("s8-balkentitel", an(2, takt))} {...taktAn(2)}>
        {kopf}
      </p>
      <ol className={k("s8-balken", an(2, takt))} {...taktAn(2)} aria-label={kopf}>
        {(t?.zeilen ?? []).map(([name = "", wert = ""], i) => {
          const v = zahlWert(wert);
          const anteil = Number.isFinite(gesamt) && gesamt > 0 ? Math.min(1, v / gesamt) : 0;
          return (
            <li key={i} className={k("s8-zeile")}>
              <p className={k("s8-name", "a")} style={vars({ t: 0.2 + i * 0.2 })}>
                {name}
              </p>
              <div className={k("s8-spur")}>
                {v === 0 ? (
                  <>
                    <span className={k("s8-zahl", "a")} style={vars({ t: 1.1 })}>
                      {wert}
                    </span>
                    <Haken klasse="s8-haken" viewBox="0 0 48 42" d="M7 22l11 11L42 8" t={1.3} />
                    {treffer && (
                      <span className={k("s8-trifft", "a")} style={vars({ t: 1.6 })}>
                        {treffer}
                      </span>
                    )}
                  </>
                ) : (
                  <>
                    <span className={k("s8-wert")} style={vars({ v: anteil.toFixed(4), t: 0.3 + i * 0.2 })} />
                    <span className={k("s8-zahl", "a")} style={vars({ t: 0.8 + i * 0.2 })}>
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
        <p className={k("s8-satz", an(3, takt))} {...taktAn(3)}>
          {satz}
        </p>
      )}
      <Fuss folie={folie} />
    </>
  );
}
