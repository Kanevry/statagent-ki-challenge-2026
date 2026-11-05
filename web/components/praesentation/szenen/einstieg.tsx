import { inlineText } from "../../../lib/praesentation/markdown";
import { absatzTexte, frontmatterListe, kopfUndRest, kopfzeile, listenPunkte } from "../../../lib/praesentation/szenen-daten";
import { an, Fuss, Getippt, Haken, k, Kopf, Kreis, taktAn, Text, vars, type SzeneProps } from "./gemeinsam";

// Gestaltung: links die Kreise 3, 2, 1 auf einer Linie, je Takt eine Antwort daneben; Zuläufe in den Kreis 4 rechts.
const KREISE = [
  { n: 3, y: 330, t: 1.1 },
  { n: 2, y: 520, t: 1.25 },
  { n: 1, y: 710, t: 1.4 },
] as const;
const ANTWORT_OBEN = [366, 510, 723] as const;
const ZULAEUFE = [
  "M1290 390C1420 390 1420 580 1530 580",
  "M1290 580C1420 580 1420 580 1530 580",
  "M1290 770C1420 770 1420 580 1530 580",
] as const;

/**
 * Szene 9 (drei Takte): Die Frage aus dem ersten Absatz tippt sich. Je Takt eine Antwort der Liste neben Kreis 3, 2, 1:
 * mit Haken, wenn ihr fetter Name in `belegt` (Frontmatter) steht, sonst mit leerem, gestricheltem Kreis (Zielbild). Im dritten Takt laufen drei Mint-Linien in den wachsenden Kreis 4, darunter der zweite Absatz.
 */
export function Einstieg({ folie, aktiv, takt }: SzeneProps) {
  const [frage = "", einstieg] = absatzTexte(folie);
  const antworten = listenPunkte(folie).slice(0, 3);
  const belegt = new Set(frontmatterListe(folie.daten.belegt));
  return (
    <>
      <Kopf titel={kopfzeile(folie)} t={0.05} ohneUc={folie.daten.ohne_uc === "ja"} />
      <p className={k("s9-frage")}>
        <Getippt text={frage} aktiv={aktiv} start={400} ms={9} />
      </p>
      <svg className={k("s9-netz")} viewBox="0 0 1920 1080" aria-hidden="true">
        <path className={k("strich", "s9-bahn", "zeichnet")} style={vars({ t: 1.2 })} pathLength={1} d="M260 340V840" />
        <g className={k(an(3, takt))} {...taktAn(3)}>
          {ZULAEUFE.map((d) => (
            <path key={d} className={k("strich", "s9-zulauf", "zeichnet")} style={vars({ t: 0.8 })} pathLength={1} d={d} />
          ))}
        </g>
      </svg>
      {KREISE.map((c) => (
        <Kreis key={c.n} n={c.n} x={200} y={c.y} d={120} t={c.t} flip={false} />
      ))}
      {antworten.map((p, i) => {
        const ja = belegt.has(inlineText(kopfUndRest(p).kopf));
        return (
          <p
            key={i}
            className={k("s9-antwort", an(i + 1, takt))}
            {...taktAn(i + 1)}
            data-belegt={ja ? "ja" : "nein"}
            style={{ top: ANTWORT_OBEN[i] }}
          >
            {ja ? (
              <Haken viewBox="0 0 40 36" d="M6 19l9 9L34 8" t={0.3} />
            ) : (
              <svg className={k("s9-offen")} viewBox="0 0 40 36" aria-hidden="true">
                <circle cx="20" cy="18" r="14" />
              </svg>
            )}
            <span>
              <span className="sr-only">{ja ? "Belegt: " : "Noch nicht belegt: "}</span>
              <Text inline={p} />
            </span>
          </p>
        );
      })}
      <Kreis n={4} x={1530} y={470} d={220} klasse="s9-k4" ab={3} takt={takt} />
      {einstieg && (
        <p className={k("s9-einstieg", an(3, takt))} {...taktAn(3)} style={vars({ tt: 1.9 })}>
          {einstieg}
        </p>
      )}
      <Fuss folie={folie} />
    </>
  );
}
