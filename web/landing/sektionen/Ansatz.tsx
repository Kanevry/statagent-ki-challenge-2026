import type { CSSProperties, ReactNode } from "react";
import { ANSATZ } from "../texte/inhalt";
import a from "./abschnitte.module.css";
import Einblenden from "./Einblenden";
import s from "./seite.module.css";

/** Kleine Bilder je Regel: Strich in Tinte, das, worum es geht, in Grün. */
const BILDER: Record<(typeof ANSATZ.punkte)[number]["bild"], ReactNode> = {
  // Code links, daraus entstehen rechts Zahlen in einer Tabelle
  rechnen: (
    <>
      <path d="M9 13 3 20l6 7M17 13l6 7-6 7" />
      <path d="M28 20h6" data-gruen="" />
      <rect x="37" y="9" width="24" height="22" rx="2" />
      <path d="M37 16h24M37 23h24M49 9v22" />
    </>
  ),
  // Datenbank, daneben zwei Fassungen einer Regel: die alte bleibt, durchgestrichen
  regeln: (
    <>
      <ellipse cx="15" cy="10" rx="11" ry="4" />
      <path d="M4 10v20c0 2.2 4.9 4 11 4s11-1.8 11-4V10M4 20c0 2.2 4.9 4 11 4s11-1.8 11-4" />
      <path d="M36 12h24M36 18h14" />
      <path d="M36 28h24" data-gruen="" />
    </>
  ),
  // Unterschrift auf einer Linie
  freigabe: (
    <>
      <path d="M4 33h56" />
      <path d="M8 27c5-11 9-17 11-15 3 3-6 15-3 16 3 1 6-8 9-7 2 .8 0 6 3 6s6-5 9-5 2 4 5 4 6-2 9-3" data-gruen="" />
    </>
  ),
  // Zahl, von der ein Faden zur Abfrage führt
  beleg: (
    <>
      <rect x="3" y="8" width="20" height="14" rx="2" data-gruen="" />
      <path d="M23 15h9c3 0 3 8 6 8h1" />
      <rect x="39" y="10" width="22" height="26" rx="2" />
      <path d="M44 17h12M44 23h12M44 29h7" />
    </>
  ),
  // Rechner als Schutzraum, Daten bleiben drin, nach außen geht nur eine Linie mit Sperre
  lokal: (
    <>
      <rect x="4" y="6" width="36" height="24" rx="2" />
      <path d="M15 36h14M22 30v6" />
      <path d="M12 14h6v8h-6zM22 14h10M22 19h10M22 24h6" data-gruen="" />
      <path d="M46 18h15M52 13l5 10M57 13l-5 10" />
    </>
  ),
};

/** „So arbeiten wir“: fünf Regeln, je ein Bild und ein Satz. */
export default function Ansatz() {
  return (
    <section id="ansatz" className={s.abschnitt} aria-labelledby="ansatz-titel">
      <div className={s.rahmen}>
        <header className={s.kopf}>
          <h2 id="ansatz-titel" className={s.titel}>
            {ANSATZ.titel}
          </h2>
          <p className={s.einleitung}>{ANSATZ.einleitung}</p>
        </header>

        <Einblenden className={s.einblenden}>
          <ul className={a.regeln}>
            {ANSATZ.punkte.map((punkt, i) => (
              <li key={punkt.titel} className={`${s.zeile} ${a.regel}`} style={{ "--i": i } as CSSProperties}>
                <svg className={a.regelBild} viewBox="0 0 64 40" aria-hidden="true">
                  {BILDER[punkt.bild]}
                </svg>
                <div>
                  <h3 className={a.regelTitel}>{punkt.titel}</h3>
                  <p className={a.regelText}>{punkt.text}</p>
                </div>
              </li>
            ))}
          </ul>
        </Einblenden>

        <p className={a.modell}>
          <span>{ANSATZ.modell.text}</span>{" "}
          {ANSATZ.modell.anbieter.map((m, i) => (
            <span key={m.name} className={a.anbieter}>
              <code className={a.anbieterName}>{m.name}</code>
              {"zusatz" in m ? <span className={a.anbieterZusatz}> ({m.zusatz})</span> : null}
              {i < ANSATZ.modell.anbieter.length - 1 ? ", " : "."}
            </span>
          ))}
        </p>
      </div>
    </section>
  );
}
