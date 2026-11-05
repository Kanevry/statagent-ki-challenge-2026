import { absatzTexte, tabelle } from "../../../lib/praesentation/szenen-daten";
import { Fuss, Getippt, k, Kreis, vars, type SzeneProps } from "./gemeinsam";

// Gestaltung: Spalten links, Mitte, rechts; Zeitplan je Spalte wie im Prototyp (Sekunden bzw. ms).
const SPALTEN = [
  { links: 140, kreisX: 300, person: 0.5, tippen: 650, uc: 1.1 },
  { links: 700, kreisX: 860, person: 1.2, tippen: 1350, uc: 2.15 },
  { links: 1260, kreisX: 1420, person: 2.25, tippen: 2400, uc: 3 },
] as const;

/**
 * Szene 2: die drei Kreise rücken auseinander, darunter je Person, Frage (tippt sich) und Use Case aus der Tabelle.
 * Die Zeile, deren Aufgabe in `hervorheben` steht, bekommt den Mint-Chip. Darunter Satz und Linie.
 */
export function DreiFragen({ folie, nr, aktiv }: SzeneProps) {
  const zeilen = tabelle(folie)?.zeilen ?? [];
  const [satz] = absatzTexte(folie);
  return (
    <>
      {zeilen.slice(0, 3).map(([aufgabe = "", person = "", frage = "", uc = ""], i) => {
        const s = SPALTEN[i] ?? SPALTEN[0];
        const n = Number(aufgabe) || i + 1;
        return (
          <div key={i}>
            <Kreis n={n} x={s.kreisX} y={140} d={200} t={0.1 * (i + 1)} />
            <div className={k("s2-spalte")} style={{ left: s.links }}>
              <p className={k("s2-person", "a")} style={vars({ t: s.person })}>
                {person}
              </p>
              <p className={k("s2-frage")} aria-label={frage}>
                <Getippt text={frage} aktiv={aktiv} start={s.tippen} ms={15} />
              </p>
              <p className={k("s2-uc", "a")} style={vars({ t: s.uc })}>
                {aufgabe === folie.daten.hervorheben ? <span className={k("s2-chip")}>{uc}</span> : uc}
              </p>
            </div>
          </div>
        );
      })}
      {satz && (
        <p className={k("s2-satz", "a")} style={vars({ t: 3.4 })}>
          {satz}
        </p>
      )}
      <div className={k("s2-linie")} aria-hidden="true" />
      <Fuss folie={folie} nr={nr} />
    </>
  );
}
