import { inlineText } from "../../../lib/praesentation/markdown";
import { kopfzeile, listenPunkte } from "../../../lib/praesentation/szenen-daten";
import { Blick, Fuss, Getippt, k, Kreis, vars, type SzeneProps } from "./gemeinsam";

// Gestaltung: je Baustein Lage, Fallzeit und Zeichen (Haken, Unterschrift, zwei Pfeile im Kreis), von unten nach oben.
const STEINE = [
  { top: 272, t: 0.3 },
  { top: 136, t: 0.8 },
  { top: 0, t: 1.3 },
] as const;

function Zeichen({ nr }: { nr: number }) {
  if (nr === 0) {
    return (
      <svg className={k("s4-zeichen", "haken")} viewBox="0 0 72 64" aria-hidden="true">
        <path className={k("strich", "zeichnet")} style={vars({ t: 1 })} pathLength={1} d="M10 34l16 16L62 12" />
      </svg>
    );
  }
  if (nr === 1) {
    return (
      <svg className={k("s4-zeichen", "s4-unterschrift")} viewBox="0 0 72 64" aria-hidden="true">
        <path
          className={k("strich", "zeichnet")}
          style={vars({ t: 1.5, dauer: "0.5s" })}
          pathLength={1}
          d="M4 44c8-22 14-30 18-24s-6 24 2 22 10-26 16-22-2 20 6 18 12-14 22-10"
        />
      </svg>
    );
  }
  return (
    <svg className={k("s4-zeichen", "s4-pfeile")} viewBox="0 0 72 64" aria-hidden="true">
      <path className={k("strich", "zeichnet")} style={vars({ t: 2, dauer: "0.5s" })} pathLength={1} d="M14 30a22 22 0 0 1 40-10M50 8l4 12-12 2" />
      <path className={k("strich", "zeichnet")} style={vars({ t: 2.15, dauer: "0.5s" })} pathLength={1} d="M58 34a22 22 0 0 1-40 10M22 56l-4-12 12-2" />
    </svg>
  );
}

/**
 * Szene 4: Die drei Regeln der Liste fallen als Bausteine von oben und rasten ein (erster Punkt unten). Unter der
 * zweiten Regel tippt sich der Name aus `name`. Dann landen die Kreise 1, 2, 3 auf dem Stapel.
 */
export function Kern({ folie, nr, aktiv }: SzeneProps) {
  const regeln = listenPunkte(folie).map(inlineText);
  const name = folie.daten.name;
  return (
    <>
      <h2 className={k("titel", "ohne-kreis", "a")} style={vars({ t: 0.1 })}>
        {kopfzeile(folie)}
      </h2>
      <ol className={k("s4-stapel")}>
        {regeln.slice(0, 3).map((regel, i) => (
          <li key={i} className={k("s4-stein")} style={{ top: STEINE[i]?.top, ...vars({ t: STEINE[i]?.t ?? 0 }) }}>
            <Zeichen nr={i} />
            <p className={k("s4-text")}>
              {regel}
              {i === 1 && name && (
                <span className={k("s4-name")} aria-label={name}>
                  <Getippt text={name} aktiv={aktiv} start={2000} ms={24} />
                </span>
              )}
            </p>
          </li>
        ))}
      </ol>
      {[1, 2, 3].map((n, i) => (
        <Kreis key={n} n={n} x={285 + i * 250} y={334} d={150} t={2.5 + i * 0.15} klasse="s4-kr" />
      ))}
      <Blick folie={folie} breite={620} t={3.5} style={{ bottom: 180 }} />
      <Fuss folie={folie} nr={nr} />
    </>
  );
}
