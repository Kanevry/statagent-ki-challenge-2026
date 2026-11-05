import { absatzTexte, kopfzeile, tabelle, zahlWert } from "../../../lib/praesentation/szenen-daten";
import { Fuss, k, vars, type SzeneProps } from "./gemeinsam";

/**
 * Szene 7: je Variante ein Balken, Länge = Wert / Gesamtzahl aus dem Spaltenkopf („… von 576“). Eine Variante mit 0
 * bekommt statt des Balkens den Mint-Haken und „trifft alle N Zellen“.
 */
export function Annahme({ folie, nr }: SzeneProps) {
  const t = tabelle(folie);
  const kopf = t?.kopf[2] ?? "";
  const gesamtText = /von\s+([\d.]+)/.exec(kopf)?.[1] ?? "";
  const gesamt = zahlWert(gesamtText);
  const [unter, schluss] = absatzTexte(folie);
  return (
    <>
      <h2 className={k("titel", "a")} style={vars({ i: 0 })}>
        {kopfzeile(folie)}
      </h2>
      {unter && (
        <p className={k("unterzeile", "s7-unter", "a")} style={vars({ i: 1 })}>
          {unter}
        </p>
      )}
      <ol className={k("s7-balken")} aria-label={kopf}>
        {(t?.zeilen ?? []).map(([variante = "", behandlung = "", wert = ""], i) => {
          const v = zahlWert(wert);
          const anteil = Number.isFinite(gesamt) && gesamt > 0 ? Math.min(1, v / gesamt) : 0;
          return (
            <li key={i} className={k("s7-zeile")}>
              <p className={k("s7-name")}>
                <span className={k("s7-variante")}>{variante}</span>
                {behandlung}
              </p>
              <div className={k("s7-spur")}>
                {v === 0 ? (
                  <>
                    <svg className={k("s7-haken")} viewBox="0 0 40 36" aria-hidden="true">
                      <path pathLength={1} d="M6 19l9 9L34 8" />
                    </svg>
                    <span className={k("s7-trifft")}>{`trifft alle ${gesamtText} Zellen`}</span>
                  </>
                ) : (
                  <>
                    <span className={k("s7-balken-wert")} style={vars({ v: anteil.toFixed(4), i })} />
                    <span className={k("s7-zahl")} style={vars({ i })}>
                      {wert}
                    </span>
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      {schluss && (
        <p className={k("s7-schluss", "a")} style={vars({ i: 30 })}>
          {schluss}
        </p>
      )}
      <Fuss folie={folie} nr={nr} />
    </>
  );
}
