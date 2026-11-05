import { kopfzeile, listenPunkte, tabelle, zahlWert } from "../../../lib/praesentation/szenen-daten";
import { Fuss, k, Kopf, Text, vars, type SzeneProps } from "./gemeinsam";

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
 * Szene 3 (drei Takte): Säulen aus der Tabelle, Achse ab 0. Die Säule aus `monat_bruch` fällt in Takt 1 auf
 * `zahl_geliefert` (gelb, rechts groß mit `vergleich`), bekommt in Takt 2 den `stempel` und steigt in Takt 3 als
 * gefüllter Mint-Balken mit Haken zurück (rechts `vorlaeufig`). Die Takt-Sätze sind die Liste.
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
  const { zahl_geliefert: geliefert, vergleich, vorlaeufig, stempel } = folie.daten;

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
              style={vars({ i, h: hoehe(r.zahl), ...(i === bruch ? { hg: hoehe(zahlWert(geliefert)) } : {}) })}
            >
              <div className={k("s3-fuellung")} />
              {i === bruch && (
                <>
                  <div className={k("s3-marke")} />
                  {stempel && <p className={k("s3-stempel")}>{stempel}</p>}
                  <svg className={k("s3-haken", "haken")} viewBox="0 0 64 56" aria-hidden="true">
                    <path className={k("strich")} pathLength={1} d="M8 30l14 14L56 10" />
                  </svg>
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
        {geliefert && (
          <p className={k("s3-r1")}>
            <b>{geliefert}</b>
            {vergleich && <span>{vergleich}</span>}
          </p>
        )}
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
