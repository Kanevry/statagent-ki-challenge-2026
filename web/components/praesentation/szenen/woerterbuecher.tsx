import { absatzTexte, kopfzeile, tabellen, uebergaenge } from "../../../lib/praesentation/szenen-daten";
import { Fuss, k, Kopf, vars, type SzeneProps } from "./gemeinsam";

// Gestaltung: Lage der Kästchen (links und rechts), Linien von Kästchenrand zu Kästchenrand, Zeitplan in Sekunden.
const LINKS = { x: 120, rand: 760, oben: 300, abstand: 130, t: 0.3 } as const;
const RECHTS = { x: 1100, oben: 290, abstand: 110, t: 0.8 } as const;
const HALB = 40;

/**
 * Szene 7 (ohne Takt): zwei Branchenlisten aus den beiden Tabellen (Kopf: Name und Gültigkeit), dazwischen die
 * Übergänge aus `uebergang` („C-C J-J Q-R J-K“). Ein alter Code mit zwei Zielen teilt sich: die zweite Linie läuft
 * gelb, ihr Zielkästchen bekommt einen gelben Rand. Darunter die beiden Absätze.
 */
export function Woerterbuecher({ folie }: SzeneProps) {
  const [alt, neu] = tabellen(folie);
  const [teilt, satz] = absatzTexte(folie);
  const altCodes = (alt?.zeilen ?? []).map((z) => z[0] ?? "");
  const neuCodes = (neu?.zeilen ?? []).map((z) => z[0] ?? "");
  const gesehen = new Set<string>();
  const linien = uebergaenge(folie.daten.uebergang)
    .map(([von, nach]) => {
      const li = altCodes.indexOf(von);
      const rj = neuCodes.indexOf(nach);
      const geteilt = gesehen.has(von);
      gesehen.add(von);
      return { li, rj, geteilt, nach };
    })
    .filter((l) => l.li >= 0 && l.rj >= 0);
  const gelbeZiele = new Set(linien.filter((l) => l.geteilt).map((l) => l.nach));
  let grau = 0;

  return (
    <>
      <Kopf titel={kopfzeile(folie)} />
      {[alt, neu].map((t, s) =>
        t ? (
          <p key={s} className={k("s7b-kopf", "a")} style={{ left: s === 0 ? LINKS.x : RECHTS.x, ...vars({ t: s === 0 ? 0.2 : 0.7 }) }}>
            {t.kopf[0]} <span>{`· ${t.kopf[1] ?? ""}`}</span>
          </p>
        ) : null,
      )}
      {(alt?.zeilen ?? []).map(([code = "", name = ""], i) => (
        <p key={`a${code}`} className={k("s7b-box", "s7b-links", "a")} style={{ top: LINKS.oben + i * LINKS.abstand, ...vars({ t: LINKS.t + i * 0.1 }) }}>
          <b>{code}</b>
          {name}
        </p>
      ))}
      {(neu?.zeilen ?? []).map(([code = "", name = ""], j) => (
        <p
          key={`n${code}`}
          className={k("s7b-box", "s7b-rechts", gelbeZiele.has(code) ? "s7b-split" : "a")}
          style={{ top: RECHTS.oben + j * RECHTS.abstand, ...vars({ t: RECHTS.t + j * 0.1 }) }}
        >
          <b>{code}</b>
          {name}
        </p>
      ))}
      <svg className={k("s7b-netz")} viewBox="0 0 1920 1080" aria-hidden="true">
        {linien.map((l, i) => {
          const y1 = LINKS.oben + l.li * LINKS.abstand + HALB;
          const y2 = RECHTS.oben + l.rj * RECHTS.abstand + HALB;
          const t = l.geteilt ? 1.8 : 1.3 + 0.1 * grau++;
          return (
            <path
              key={i}
              className={k("strich", l.geteilt ? "s7b-gelb" : "s7b-grau", "zeichnet")}
              style={vars({ t, ...(l.geteilt ? { dauer: "0.5s" } : {}) })}
              pathLength={1}
              d={`M${LINKS.rand} ${y1}C930 ${y1} 930 ${y2} ${RECHTS.x} ${y2}`}
            />
          );
        })}
      </svg>
      {teilt && (
        <p className={k("s7b-teilt", "a")} style={vars({ t: 2.4 })}>
          {teilt}
        </p>
      )}
      {satz && (
        <p className={k("s7b-satz", "a")} style={vars({ t: 2.9 })}>
          {satz}
        </p>
      )}
      <Fuss folie={folie} />
    </>
  );
}
