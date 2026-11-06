import { ABLAUF } from "../daten/ablauf";
import g from "./ablauf.module.css";

/** Seite „Ablauf“: eine Spalte in Fließtext-Breite, ohne Bewegung. Alle Inhalte stehen in daten/ablauf.ts. */
export default function Ablauf() {
  return (
    <article className={g.ablauf}>
      <h1 className={g.titel}>{ABLAUF.titel}</h1>
      <p className={g.satz}>{ABLAUF.satz}</p>
      <p className={g.zahlen}>{ABLAUF.zahlen}</p>

      <section aria-labelledby="ablauf-zeit">
        <h2 id="ablauf-zeit" className={g.h2}>
          {ABLAUF.ueberschriften.zeitleiste}
        </h2>
        <ol className={g.zeitleiste}>
          {ABLAUF.zeitleiste.map((p) => (
            <li key={p.iso}>
              <time dateTime={p.iso}>{p.zeit}</time>
              <span>{p.satz}</span>
            </li>
          ))}
        </ol>
      </section>

      {ABLAUF.abschnitte.map((a) => (
        <section key={a.id} aria-labelledby={`ablauf-${a.id}`}>
          <h2 id={`ablauf-${a.id}`} className={g.h2}>
            {a.titel}
          </h2>
          {a.saetze.map((satz) => (
            <p key={satz} className={g.absatz}>
              {satz}
            </p>
          ))}
        </section>
      ))}
    </article>
  );
}
