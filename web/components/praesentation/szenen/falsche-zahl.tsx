import { inlineText } from "../../../lib/praesentation/markdown";
import { kopfzeile, listenPunkte, tabelle, zahlWert } from "../../../lib/praesentation/szenen-daten";
import { Fuss, k, vars, type SzeneProps } from "./gemeinsam";

/** Takte der Szene: 1 gelieferter Wert, 2 Stempel, 3 Wert wieder da. */
export const TAKTE_FALSCHE_ZAHL = 3;

// Gestaltung, kein Inhalt: Achse von 300.000 bis 400.000 und die Breite der Säulenfläche in px.
const ACHSE_UNTEN = 300_000;
const ACHSE_SPANNE = 100_000;
const BREITE = 930;
const LUECKE = 11;
const FORMAT = new Intl.NumberFormat("de-DE");

const hoehe = (v: number) => Math.min(1, Math.max(0, (v - ACHSE_UNTEN) / ACHSE_SPANNE)).toFixed(4);

/** Szene 2: 24 Säulen aus der Tabelle, die Säule aus `monat_bruch` fällt auf `zahl_geliefert` und steigt wieder. */
export function FalscheZahl({ folie, nr, takt }: SzeneProps) {
  const t = tabelle(folie);
  const reihen = (t?.zeilen ?? []).map(([monat = "", wert = ""]) => ({ monat, wert, zahl: zahlWert(wert) }));
  const bruch = reihen.findIndex((r) => r.monat === folie.daten.monat_bruch);
  const geliefert = folie.daten.zahl_geliefert;
  const n = Math.max(reihen.length, 1);
  const w = (BREITE - LUECKE * (n - 1)) / n;
  const spalte = (i: number) => i * (w + LUECKE) + w / 2;
  const beschriftet = [0, bruch, reihen.length - 1].filter((i, j, alle) => i >= 0 && alle.indexOf(i) === j);
  const saetze = listenPunkte(folie).map(inlineText);
  const erste = reihen[0]?.monat ?? "";
  const letzte = reihen.at(-1)?.monat ?? "";

  return (
    <div className={k(takt >= 1 && "takt-1", takt >= 2 && "takt-2", takt >= 3 && "takt-3")}>
      <h2 className={k("titel", "a")} style={vars({ i: 0 })}>
        {kopfzeile(folie)}
      </h2>
      <div className={k("s2-diagramm")} role="img" aria-label={`${t?.kopf[1] ?? ""}, ${erste} bis ${letzte}`}>
        <p className={k("s2-achse", "s2-oben")}>{FORMAT.format(ACHSE_UNTEN + ACHSE_SPANNE)}</p>
        <p className={k("s2-achse", "s2-unten")}>{FORMAT.format(ACHSE_UNTEN)}</p>
        <div className={k("s2-saeulen")}>
          {reihen.map((r, i) => (
            <div
              key={r.monat}
              className={k("s2-saeule", i === bruch && "s2-okt")}
              style={vars({ i, h: hoehe(r.zahl), ...(i === bruch ? { "h-geliefert": hoehe(zahlWert(geliefert)) } : {}) })}
            >
              <div className={k("s2-fuellung")} />
              {i === bruch && (
                <>
                  <div className={k("s2-marke")} />
                  <p className={k("s2-stempel")}>angehalten</p>
                </>
              )}
            </div>
          ))}
        </div>
      </div>
      <div className={k("s2-monate")}>
        {beschriftet.map((i) => (
          <p key={i} className={k("s2-monat")} style={{ left: spalte(i) }}>
            {reihen[i]?.monat}
          </p>
        ))}
        {bruch >= 0 && geliefert && (
          <p className={k("s2-notiz", "s2-gelb")} style={{ left: spalte(bruch) }}>
            {`${geliefert} so geliefert`}
          </p>
        )}
        {bruch >= 0 && (
          <p className={k("s2-notiz", "s2-mint")} style={{ left: spalte(bruch) }}>
            {`${reihen[bruch]?.wert ?? ""} vorläufig`}
          </p>
        )}
      </div>
      <ol className={k("s2-saetze")}>
        {saetze.map((satz, i) => (
          <li key={i} className={k(`t${i + 1}`)}>
            {satz}
          </li>
        ))}
      </ol>
      <Fuss folie={folie} nr={nr} />
    </div>
  );
}
