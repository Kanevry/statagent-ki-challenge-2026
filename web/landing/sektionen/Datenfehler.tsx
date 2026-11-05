import type { Einstufung } from "../daten/fakten";
import type { BefundTabelle, BefundZeile } from "../daten/typen";
import { DATENFEHLER } from "../texte/inhalt";
import a from "./abschnitte.module.css";
import Einblenden from "./Einblenden";
import s from "./seite.module.css";

const ZEICHEN: Record<Einstufung, string> = {
  "erklaert-plausibel": "✓",
  "erklaert-datenproblem": "✓",
  "nicht-erklaerbar": "!",
  revision: "Δ",
};

function standText(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const zwei = (n: number) => String(n).padStart(2, "0");
  return `${zwei(d.getDate())}.${zwei(d.getMonth() + 1)}.${d.getFullYear()}, ${zwei(d.getHours())}:${zwei(d.getMinutes())}`;
}

function Einstufungstext({ zeile }: { zeile: BefundZeile }) {
  return (
    <span className={zeile.einstufung === "nicht-erklaerbar" ? a.warn : a.ok}>
      <span className={a.zeichen} aria-hidden="true">
        {ZEICHEN[zeile.einstufung]}
      </span>
      <span>{zeile.einstufungText}</span>
      {zeile.rueckfrage ? (
        <span>
          {" · "}
          {DATENFEHLER.rueckfrage} {zeile.rueckfrage}
        </span>
      ) : null}
    </span>
  );
}

/** „Gefundene Datenfehler“: Befunde der Prüfung; Desktop als Tabelle, mobil als Liste mit Trennlinien. */
export default function Datenfehler({ tabelle }: { tabelle: BefundTabelle }) {
  const sp = DATENFEHLER.spalten;
  return (
    <section id="datenfehler" className={s.abschnitt} aria-labelledby="datenfehler-titel">
      <div className={s.rahmen}>
        <header className={s.kopf}>
          <h2 id="datenfehler-titel" className={s.titel}>
            {DATENFEHLER.titel}
          </h2>
          <p className={s.einleitung}>{DATENFEHLER.unterzeile}</p>
          <p className={s.einleitung}>{DATENFEHLER.einleitung}</p>
        </header>

        <Einblenden className={s.einblenden}>
          <div className={s.block}>
            <p className={tabelle.quelle === "beispieldaten" ? a.quelleBeispiel : a.quelleLive}>
              {tabelle.quelle === "beispieldaten"
                ? tabelle.grund === "keine-treffer"
                  ? DATENFEHLER.keineTreffer
                  : DATENFEHLER.beispieldaten
                : `${DATENFEHLER.datenbank} ${standText(tabelle.stand)}.`}
              {tabelle.quelle === "datenbank" && tabelle.anzahl > tabelle.zeilen.length
                ? ` ${DATENFEHLER.auswahl(tabelle.zeilen.length, tabelle.anzahl)}`
                : null}
            </p>

            <table className={a.befunde}>
              <caption className={s.nurLeser}>{DATENFEHLER.beschriftung}</caption>
              <thead>
                <tr>
                  <th scope="col">{sp.befund}</th>
                  <th scope="col">{sp.lieferung}</th>
                  <th scope="col">{sp.saetze}</th>
                  <th scope="col">{sp.einstufung}</th>
                </tr>
              </thead>
              <tbody>
                {tabelle.zeilen.map((z, i) => (
                  <tr key={`${z.befund}-${z.lieferung}-${i}`}>
                    <th scope="row">
                      <span className={a.befundName}>{z.befund}</span>
                      {z.beleg ? <code className={a.befundBeleg}>{z.beleg}</code> : null}
                    </th>
                    <td className={a.mono}>{z.lieferung}</td>
                    <td className={a.mono}>{z.saetze}</td>
                    <td>
                      <Einstufungstext zeile={z} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <ul className={a.befundListe} aria-label={DATENFEHLER.beschriftung}>
              {tabelle.zeilen.map((z, i) => (
                <li key={`${z.befund}-${z.lieferung}-${i}`} className={a.befundEintrag}>
                  <p className={a.befundName}>{z.befund}</p>
                  <dl className={a.befundDaten}>
                    <div>
                      <dt>{sp.lieferung}</dt>
                      <dd className={a.mono}>{z.lieferung}</dd>
                    </div>
                    <div>
                      <dt>{sp.saetze}</dt>
                      <dd className={a.mono}>{z.saetze}</dd>
                    </div>
                    <div>
                      <dt>{sp.einstufung}</dt>
                      <dd>
                        <Einstufungstext zeile={z} />
                      </dd>
                    </div>
                  </dl>
                  {z.beleg ? <code className={a.befundBeleg}>{z.beleg}</code> : null}
                </li>
              ))}
            </ul>

            <dl className={a.glossar}>
              {DATENFEHLER.glossar.map((g) => (
                <div key={g.begriff}>
                  <dt>{g.begriff}</dt>
                  <dd>{g.erklaerung}</dd>
                </div>
              ))}
            </dl>
          </div>
        </Einblenden>
      </div>
    </section>
  );
}
