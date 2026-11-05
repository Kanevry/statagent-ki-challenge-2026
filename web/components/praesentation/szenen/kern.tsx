import { inlineText } from "../../../lib/praesentation/markdown";
import { absatzTexte, kopfzeile, listenPunkte } from "../../../lib/praesentation/szenen-daten";
import { an, Blick, Fuss, Getippt, k, Kopf, Kreis, taktAn, vars, type SzeneProps } from "./gemeinsam";

// Gestaltung: Lage je Regel (von oben), Zeichen je Regel, Kreise rechts daneben (ohne Flug, der Kopf hat Kreis 3).
const OBEN = [250, 380, 570] as const;

function Zeichen({ nr }: { nr: number }) {
  if (nr === 0) {
    return (
      <svg className={k("s4-zeichen", "haken")} viewBox="0 0 72 64" aria-hidden="true">
        <path className={k("strich", "zeichnet")} style={vars({ t: 0.3 })} pathLength={1} d="M10 34l16 16L62 12" />
      </svg>
    );
  }
  if (nr === 1) {
    return (
      <svg className={k("s4-zeichen", "s4-unterschrift")} viewBox="0 0 72 64" aria-hidden="true">
        <path
          className={k("strich", "zeichnet")}
          style={vars({ t: 0.3, dauer: "0.5s" })}
          pathLength={1}
          d="M4 44c8-22 14-30 18-24s-6 24 2 22 10-26 16-22-2 20 6 18 12-14 22-10"
        />
      </svg>
    );
  }
  return (
    <svg className={k("s4-zeichen", "s4-pfeile")} viewBox="0 0 72 64" aria-hidden="true">
      <path className={k("strich", "zeichnet")} style={vars({ t: 0.3, dauer: "0.5s" })} pathLength={1} d="M14 30a22 22 0 0 1 40-10M50 8l4 12-12 2" />
      <path className={k("strich", "zeichnet")} style={vars({ t: 0.45, dauer: "0.5s" })} pathLength={1} d="M58 34a22 22 0 0 1-40 10M22 56l-4-12 12-2" />
    </svg>
  );
}

/**
 * Szene 4 (drei Takte, je Regel einer): reine Textzeilen mit gezeichnetem Zeichen, ohne Flächen. Unter der zweiten
 * Regel tippt sich `name`, danach gleitet das echte Bild herein (bilder.ts). Mit der dritten landen die Kreise.
 * Unten klein der erste Absatz, ab Beginn.
 */
export function Kern({ folie, aktiv, takt }: SzeneProps) {
  const regeln = listenPunkte(folie).map(inlineText);
  const [fuss] = absatzTexte(folie);
  const name = folie.daten.name;
  return (
    <>
      <Kopf titel={kopfzeile(folie)} />
      <ol className={k("s4-regeln")}>
        {regeln.slice(0, 3).map((regel, i) => {
          const saetze = regel.split(/(?<=\.)\s+/);
          return (
            <li key={i} className={k("s4-regel", an(i + 1, takt))} {...taktAn(i + 1)} style={{ top: OBEN[i] }}>
              <Zeichen nr={i} />
              <p className={k("s4-text")}>
                {saetze.map((s, j) => (
                  <span key={j}>
                    {j > 0 && <br />}
                    {s}
                  </span>
                ))}
                {i === 1 && name && (
                  <span className={k("s4-name")} aria-label={name}>
                    <Getippt text={name} aktiv={aktiv && takt >= 2} start={700} ms={40} />
                  </span>
                )}
              </p>
            </li>
          );
        })}
      </ol>
      {[1, 2, 3].map((n, i) => (
        <Kreis key={n} n={n} x={950 + i * 110} y={420} d={96} t={1 + i * 0.15} klasse="s4-kr" flip={false} ab={3} takt={takt} />
      ))}
      <Blick folie={folie} ab={2} takt={takt} tt={1.7} lage={{ right: 80, top: 196, width: 546, height: 700 }} />
      {fuss && (
        <p className={k("s4-fuss", "a")} style={vars({ t: 0.6 })}>
          {fuss}
        </p>
      )}
      <Fuss folie={folie} />
    </>
  );
}
