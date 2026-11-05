import { kopfzeile, listenPunkte, tabelle, zahlWert } from "../../../lib/praesentation/szenen-daten";
import { Fuss, k, Kopf, Pause, Text, vars, type SzeneProps } from "./gemeinsam";

// Gestaltung, kein Inhalt: Achse von 0 bis 400.000 und die Breite der Säulenfläche in px.
const ACHSE_OBEN = 400_000;
const BREITE = 890;
const LUECKE = 10;
const FORMAT = new Intl.NumberFormat("de-DE");

// Monatsnamen für Achse (kurz) und Bildbeschreibung (lang); die Tabelle trägt Monate als Daten (JJJJ-MM).
const KURZ = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
const LANG = ["Jänner", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];

/** `2025-10` wird `Okt 2025` (kurz) bzw. `Oktober 2025` (lang); andere Formen bleiben, wie sie sind. */
export function monatText(monat: string, lang = false): string {
  const t = /^(\d{4})-(\d{2})$/.exec(monat);
  const name = t ? (lang ? LANG : KURZ)[Number(t[2]) - 1] : undefined;
  return t && name ? `${name} ${t[1]}` : monat;
}

const hoehe = (v: number) => Math.min(1, Math.max(0, v / ACHSE_OBEN)).toFixed(4);

/**
 * Szene 3 (drei Takte): Säulen aus der Tabelle, Achse ab 0. Die Säule aus `monat_bruch` fällt in Takt 1 gelb auf
 * `zahl_geliefert`, rechts steht nur `zahl_gross`. In Takt 2 bekommt sie das Pause-Zeichen (wie die angehaltenen
 * Monate in Szene 5), rechts kommt `zahl_geliefert` mit `vergleich`. In Takt 3 steigt sie gelb auf den Tabellenwert,
 * das Pause-Zeichen bleibt, rechts kommt `vorlaeufig`. Kein Haken: der Monat ist angehalten, nicht in Ordnung.
 * Die Takt-Sätze sind die Liste.
 */
export function FalscheZahl({ folie, takt }: SzeneProps) {
  const t = tabelle(folie);
  const reihen = (t?.zeilen ?? []).map(([monat = "", wert = ""]) => ({ monat, zahl: zahlWert(wert) }));
  const bruch = reihen.findIndex((r) => r.monat === folie.daten.monat_bruch);
  const n = Math.max(reihen.length, 1);
  const w = (BREITE - LUECKE * (n - 1)) / n;
  const spalte = (i: number) => i * (w + LUECKE) + w / 2;
  const letzte = reihen.length - 1;
  const beschriftet = [0, bruch, letzte].filter((i, j, alle) => i >= 0 && alle.indexOf(i) === j);
  const { zahl_gross: gross, zahl_geliefert: geliefert, vergleich, vorlaeufig } = folie.daten;
  const [, grossZahl = gross ?? "", grossRest = ""] = /^([\d.]+)\s*(.*)$/.exec(gross ?? "") ?? [];

  return (
    <div className={k(takt >= 1 && "takt-1", takt >= 2 && "takt-2", takt >= 3 && "takt-3")}>
      <Kopf titel={kopfzeile(folie)} />
      {t?.kopf[1] && (
        <p className={k("s3-was", "a")} style={vars({ t: 0.3 })}>
          {t.kopf[1]}
        </p>
      )}
      <div
        className={k("s3-diagramm")}
        role="img"
        aria-label={`${t?.kopf[1] ?? ""}, ${monatText(reihen[0]?.monat ?? "", true)} bis ${monatText(reihen[letzte]?.monat ?? "", true)}`}
      >
        <p className={k("s3-achse", "s3-oben", "a")} style={vars({ t: 0.3 })}>
          {FORMAT.format(ACHSE_OBEN)}
        </p>
        <p className={k("s3-achse", "s3-unten", "a")} style={vars({ t: 0.3 })}>
          {FORMAT.format(0)}
        </p>
        <div className={k("s3-saeulen")}>
          {reihen.map((r, i) => (
            <div
              key={r.monat}
              className={k("s3-saeule", i === bruch && "s3-okt")}
              style={vars({ i, h: hoehe(r.zahl), ...(i === bruch ? { hg: hoehe(geliefert ? zahlWert(geliefert) : r.zahl) } : {}) })}
            >
              <div className={k("s3-fuellung")} />
              {i === bruch && (
                <>
                  <div className={k("s3-marke")} />
                  <Pause klasse="s3-pause" />
                </>
              )}
            </div>
          ))}
        </div>
      </div>
      <div className={k("s3-monate")}>
        {beschriftet.map((i) => (
          <p
            key={i}
            className={k("s3-monat")}
            style={{
              left: spalte(i),
              ...(i === 0 ? { transform: "translateX(-18px)" } : i === letzte ? { transform: "translateX(calc(-100% + 18px))" } : {}),
            }}
          >
            {monatText(reihen[i]?.monat ?? "")}
          </p>
        ))}
      </div>
      <div className={k("s3-rechts")}>
        {grossZahl && (
          <p className={k("s3-r1")}>
            <b>{grossZahl}</b>
            {grossRest && (
              <>
                {" "}
                <span>{grossRest}</span>
              </>
            )}
          </p>
        )}
        {(geliefert || vergleich) && <p className={k("s3-r2")}>{[geliefert, vergleich].filter(Boolean).join(" ")}</p>}
        {vorlaeufig && <p className={k("s3-r3")}>{vorlaeufig}</p>}
      </div>
      <ol className={k("s3-takte")}>
        {listenPunkte(folie).map((p, i) => (
          <li key={i} className={k(`t${i + 1}`)}>
            <Text inline={p} />
          </li>
        ))}
      </ol>
      <Fuss folie={folie} />
    </div>
  );
}
