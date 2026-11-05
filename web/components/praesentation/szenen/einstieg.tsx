import { inlineText } from "../../../lib/praesentation/markdown";
import { absatzTexte, kopfUndRest, kopfzeile, listenPunkte } from "../../../lib/praesentation/szenen-daten";
import { Fuss, Getippt, Haken, k, Kreis, vars, type SzeneProps } from "./gemeinsam";

// Gestaltung: Kreise untereinander (Reihenfolge der Liste), Zuläufe in den Kreis 4 rechts, Zeitplan wie im Prototyp.
const ZEILE_Y = [330, 530, 730] as const;
const KREIS_T = [0, 0.3, 0.45] as const;
const ANTWORT_T = [1.55, 1.95, 2.35] as const;
const ZULAEUFE = [
  "M1080 400C1300 400 1330 610 1500 610",
  "M1080 600C1300 600 1330 610 1500 610",
  "M1080 800C1300 800 1330 610 1500 610",
] as const;

/**
 * Szene 8: Die Frage tippt sich ein. Ein Mint-Lichtpunkt läuft durch die Kreise der Liste (`**UC3:** …` ergibt
 * Kreis 3), an jedem klappt die Antwort mit Haken auf. Am Ende laufen die Linien im Kreis 4 zusammen.
 */
export function Einstieg({ folie, nr, aktiv }: SzeneProps) {
  const [frage = "", einstieg] = absatzTexte(folie);
  const antworten = listenPunkte(folie)
    .slice(0, 3)
    .map(kopfUndRest)
    .map((p, i) => ({ n: Number(/\d+/.exec(inlineText(p.kopf))?.[0]) || 3 - i, text: p.rest }));
  return (
    <>
      <h2 className={k("titel", "ohne-kreis", "a")} style={vars({ t: 0.05 })}>
        {kopfzeile(folie)}
      </h2>
      <p className={k("s8-frage")} aria-label={frage}>
        <Getippt text={frage} aktiv={aktiv} start={400} ms={9} />
      </p>
      <svg className={k("s8-netz")} viewBox="0 0 1920 1080" aria-hidden="true">
        <path className={k("strich", "s8-bahn")} pathLength={1} d="M260 312V880" />
        {ZULAEUFE.map((d) => (
          <path key={d} className={k("strich", "s8-zulauf")} style={vars({ t: 2.6 })} pathLength={1} d={d} />
        ))}
      </svg>
      {antworten.map((a, i) => (
        <Kreis key={a.n} n={a.n} x={190} y={ZEILE_Y[i] ?? 330} d={140} t={KREIS_T[i] ?? 0} />
      ))}
      <div className={k("s8-punkt")} aria-hidden="true" />
      {antworten.map((a, i) => (
        <p key={a.n} className={k("s8-antwort", "a")} style={{ top: (ZEILE_Y[i] ?? 330) + 44, ...vars({ t: ANTWORT_T[i] ?? 1.55 }) }}>
          <Haken klasse="" viewBox="0 0 40 36" d="M6 19l9 9L34 8" t={(ANTWORT_T[i] ?? 1.55) + 0.15} />
          {a.text}
        </p>
      ))}
      <Kreis n={4} x={1500} y={500} d={220} klasse="s8-k4" />
      {einstieg && (
        <p className={k("s8-einstieg", "a")} style={vars({ t: 3.6 })}>
          {einstieg}
        </p>
      )}
      <Fuss folie={folie} nr={nr} />
    </>
  );
}
