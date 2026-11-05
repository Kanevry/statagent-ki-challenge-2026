import { TEAM } from "../texte/inhalt";
import a from "./abschnitte.module.css";
import s from "./seite.module.css";

/** Team: ohne Fotos, ohne Logos, ohne erfundene Namen. */
export default function Team() {
  return (
    <section id="team" className={`${s.abschnitt} ${a.team}`} aria-labelledby="team-titel">
      <div className={s.rahmen}>
        <div className={s.kopf}>
          <h2 id="team-titel" className={s.titel}>
            {TEAM.titel}
          </h2>
          <div className={a.teamText}>
            <p className={a.teamProdukt}>{TEAM.produkt}</p>
            <p>{TEAM.text}</p>
          </div>
        </div>
      </div>
    </section>
  );
}
