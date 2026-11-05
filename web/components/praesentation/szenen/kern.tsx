import { inlineText } from "../../../lib/praesentation/markdown";
import { absatzTexte, kopfzeile, listenPunkte } from "../../../lib/praesentation/szenen-daten";
import { an, Fuss, k, Kopf, taktAn, vars, type SzeneProps } from "./gemeinsam";

// Gestaltung: Lage je Regel (von oben), Zeichen je Regel.
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
 * Szene 4 (drei Takte, je Regel einer): reine Textzeilen mit gezeichnetem Zeichen, ohne Flächen. Mit der zweiten
 * Regel kommt rechts eine ruhige Karte mit der echten Freigabe: `freigabe_name`, `freigabe_datum`, `freigabe_regel`
 * aus dem Frontmatter, je eine Zeile. Unten klein der erste Absatz, ab Beginn.
 */
export function Kern({ folie, takt }: SzeneProps) {
  const regeln = listenPunkte(folie).map(inlineText);
  const [fuss] = absatzTexte(folie);
  const { freigabe_name: name, freigabe_datum: datum, freigabe_regel: regel } = folie.daten;
  return (
    <>
      <Kopf titel={kopfzeile(folie)} />
      <ol className={k("s4-regeln")}>
        {regeln.slice(0, 3).map((text, i) => {
          const saetze = text.split(/(?<=\.)\s+/);
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
              </p>
            </li>
          );
        })}
      </ol>
      {name && (
        <div className={k("s4-karte", an(2, takt))} {...taktAn(2)} style={vars({ tt: 0.5 })}>
          <p className={k("s4-karte-name")}>{name}</p>
          {datum && <p className={k("s4-karte-datum")}>{datum}</p>}
          {regel && <p className={k("s4-karte-regel")}>{regel}</p>}
        </div>
      )}
      {fuss && (
        <p className={k("s4-fuss", "a")} style={vars({ t: 0.6 })}>
          {fuss}
        </p>
      )}
      <Fuss folie={folie} />
    </>
  );
}
