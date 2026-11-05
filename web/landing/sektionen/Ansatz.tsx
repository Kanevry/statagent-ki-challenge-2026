import type { CSSProperties } from "react";
import { ANSATZ } from "../texte/inhalt";
import a from "./abschnitte.module.css";
import Einblenden from "./Einblenden";
import s from "./seite.module.css";

/** „So arbeiten wir“: die fünf Arbeitsregeln als nummerierte Liste mit Trennlinien. */
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
          <ol className={a.regeln}>
            {ANSATZ.punkte.map((punkt, i) => (
              <li key={punkt.titel} className={`${s.zeile} ${a.regel}`} style={{ "--i": i } as CSSProperties}>
                <span className={a.nummer} aria-hidden="true">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <h3 className={a.regelTitel}>{punkt.titel}</h3>
                <div className={a.regelText}>
                  <p>{punkt.text}</p>
                  {"beispiel" in punkt ? <code className={a.trailer}>{punkt.beispiel}</code> : null}
                </div>
              </li>
            ))}
          </ol>
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
