import { absatzTexte, frontmatterListe, kopfzeile, monatsFolge, tabelle, zahlWert } from "../../../lib/praesentation/szenen-daten";
import { an, Fuss, Haken, k, Kopf, Pause, Raster, taktAn, vars, Zaehler, type SzeneProps } from "./gemeinsam";

// Gestaltung: 80 Spalten zu 5 px wie im Prototyp (2.880 Zahlen ergeben 36 Zeilen), Zeitplan in Sekunden.
const SPALTEN = 80;
const SEITEN = [
  { klasse: "s5-links", t: 0.4 },
  { klasse: "s5-rechts", t: 0.8 },
] as const;

/**
 * Szene 5 (ein Takt). Beim Betreten: links die Vorlage als graues Raster, „=“, rechts das eigene Raster, über das eine
 * Mint-Linie läuft; darunter zählt die Zahl aus dem ersten Absatz mit. Danach „=“ und Haken in Mint, groß der zweite
 * Absatz. Das Paar steht mittig. Takt 1: das Paar rückt nach links und tritt zurück, rechts kommen Kopf und
 * Unterzeile der dritten Tabellenzeile und so viele Monatsquadrate, wie sie Monate nennt, ab dem ersten Monat, der
 * dort ausgeschrieben steht. Monate aus `angehalten` (Frontmatter) tragen statt des Hakens ein gelbes Pause-Zeichen.
 * Darunter der dritte Absatz.
 */
export function BelegSzene({ folie, aktiv, takt }: SzeneProps) {
  const anzahl = zahlWert(folie.daten.zahl);
  const zeilen = tabelle(folie)?.zeilen ?? [];
  const texte = absatzTexte(folie);
  // `ohne_zaehler: ja`: die Zählzeile entfällt, wenn der Titel sie schon sagt.
  const [zaehler = "", ergebnis, satz] = folie.daten.ohne_zaehler === "ja" ? ["", ...texte] : texte;
  const [, zahl = "", rest = ""] = /^([\d.]+)(.*)$/.exec(zaehler) ?? [];
  const [monatKopf = "", monatUnter = ""] = zeilen[2] ?? [];
  const monate = zahlWert(monatKopf);
  const namen = monatsFolge(monatKopf, monate);
  const angehalten = new Set(frontmatterListe(folie.daten.angehalten));
  return (
    <>
      <Kopf titel={kopfzeile(folie)} lang />
      <div className={k("s5-paar", takt >= 1 && "s5-zurueck")}>
        {SEITEN.map((s, i) => {
          const [kopf = "", unter = ""] = zeilen[i] ?? [];
          return (
            <div key={s.klasse} className={k("s5-seite", s.klasse, "a")} style={vars({ t: s.t })}>
              <p className={k("s5-kopf")}>{kopf}</p>
              <p className={k("s5-unter")}>{unter}</p>
              {Number.isFinite(anzahl) && (
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
            </div>
          );
        })}
        <p className={k("s5-gleich")} aria-hidden="true">
          =
        </p>
        {zahl && (
          <p className={k("s5-zaehler", "a")} style={vars({ t: 0.8 })}>
            <span className="sr-only">{zaehler}</span>
            <span aria-hidden="true">
              <Zaehler ziel={zahlWert(zahl)} aktiv={aktiv} start={1200} dauer={1600} className={k("s5-zahl")} />
              {rest}
            </span>
          </p>
        )}
        {ergebnis && (
          <p className={k("s5-null", "a")} style={vars({ t: 3 })}>
            {ergebnis}
          </p>
        )}
      </div>
      {zeilen[2] && (
        <div className={k("s5-seite", "s5-monate", an(1, takt))} {...taktAn(1)} style={vars({ tt: 0.3 })}>
          <p className={k("s5-kopf")}>{monatKopf}</p>
          <p className={k("s5-unter")}>{monatUnter}</p>
          {Number.isFinite(monate) && (
            <ol className={k("s5-mon")}>
              {Array.from({ length: monate }, (_, q) => {
                const name = namen[q];
                const halt = name !== undefined && angehalten.has(name);
                return (
                  <li key={q} className={k("s5-monat", halt && "s5-angehalten")} {...(halt ? { "data-angehalten": "ja" } : {})}>
                    {name && <span className="sr-only">{halt ? `${name}, angehalten` : name}</span>}
                    {halt ? (
                      <Pause t={0.6 + q * 0.04} dauer={0.35} />
                    ) : (
                      <Haken viewBox="0 0 40 36" d="M6 19l9 9L34 8" t={0.6 + q * 0.04} dauer={0.35} />
                    )}
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      )}
      {satz && (
        <p className={k("s5-satz", an(1, takt))} {...taktAn(1)} style={vars({ tt: 1.2 })}>
          {satz}
        </p>
      )}
      <Fuss folie={folie} />
    </>
  );
}
