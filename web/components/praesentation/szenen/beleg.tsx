import { absatzTexte, kopfzeile, tabelle, zahlWert } from "../../../lib/praesentation/szenen-daten";
import { Fuss, Haken, k, Kopf, Raster, vars, Zaehler, type SzeneProps } from "./gemeinsam";

// Gestaltung: 80 Spalten zu 5 px wie im Prototyp (2.880 Zahlen ergeben 36 Zeilen), Zeitplan in Sekunden.
const SPALTEN = 80;
const SEITEN = [
  { klasse: "s5-links", t: 0.4 },
  { klasse: "s5-rechts", t: 0.8 },
  { klasse: "s5-monate", t: 3.1 },
] as const;

/**
 * Szene 5 (ohne Takt): links der offizielle Bericht als graues Raster, „=“, rechts das eigene Raster, über das eine
 * Mint-Linie läuft; darunter zählt die Zahl aus dem ersten Absatz mit. Danach „=“ und Haken in Mint, groß der zweite
 * Absatz. Rechts so viele Monatsquadrate mit Haken, wie die dritte Tabellenzeile Monate nennt.
 */
export function BelegSzene({ folie, aktiv }: SzeneProps) {
  const anzahl = zahlWert(folie.daten.zahl);
  const zeilen = tabelle(folie)?.zeilen ?? [];
  const [zaehler = "", ergebnis, satz] = absatzTexte(folie);
  const [, zahl = "", rest = ""] = /^([\d.]+)(.*)$/.exec(zaehler) ?? [];
  const monate = zahlWert(zeilen[2]?.[0]);
  return (
    <>
      <Kopf titel={kopfzeile(folie)} lang />
      {SEITEN.map((s, i) => {
        const [kopf = "", unter = ""] = zeilen[i] ?? [];
        return (
          <div key={s.klasse} className={k("s5-seite", s.klasse, "a")} style={vars({ t: s.t })}>
            <p className={k("s5-kopf")}>{kopf}</p>
            <p className={k("s5-unter")}>{unter}</p>
            {i < 2 && Number.isFinite(anzahl) && (
              <div className={k("s5-raster")} aria-hidden="true">
                <Raster
                  anzahl={anzahl}
                  spalten={SPALTEN}
                  zelle={5}
                  luecke={1}
                  farbe={i === 0 ? "--neben" : "--mint"}
                  aktiv={aktiv}
                  {...(i === 1 ? { welle: { start: 1.2, dauer: 1.6 } } : {})}
                />
              </div>
            )}
            {i === 1 && <Haken klasse="s5-haken" viewBox="0 0 480 216" d="M150 112l70 62L340 34" t={2.9} />}
            {i === 2 && Number.isFinite(monate) && (
              <ol className={k("s5-mon")} aria-hidden="true">
                {Array.from({ length: monate }, (_, q) => (
                  <li key={q} className={k("s5-monat")}>
                    <Haken viewBox="0 0 40 36" d="M6 19l9 9L34 8" t={3.4 + q * 0.04} dauer={0.35} />
                  </li>
                ))}
              </ol>
            )}
          </div>
        );
      })}
      <p className={k("s5-gleich")} aria-hidden="true">
        =
      </p>
      {zahl && (
        <p className={k("s5-zaehler", "a")} style={vars({ t: 0.8 })} aria-label={zaehler}>
          <Zaehler ziel={zahlWert(zahl)} aktiv={aktiv} start={1200} dauer={1600} className={k("s5-zahl")} />
          {rest}
        </p>
      )}
      {ergebnis && (
        <p className={k("s5-null", "a")} style={vars({ t: 3 })}>
          {ergebnis}
        </p>
      )}
      {satz && (
        <p className={k("s5-satz", "a")} style={vars({ t: 4.4 })}>
          {satz}
        </p>
      )}
      <Fuss folie={folie} />
    </>
  );
}
