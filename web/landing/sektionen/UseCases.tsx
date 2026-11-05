import * as registry from "@kic/ui/ucs";
import { ucs, type UcId } from "@kic/ui/ucs";
import Link from "next/link";
import type { CSSProperties } from "react";
import { USE_CASES } from "../texte/inhalt";
import a from "./abschnitte.module.css";
import Einblenden from "./Einblenden";
import s from "./seite.module.css";

const REIHENFOLGE: UcId[] = ["uc3", "uc1", "uc2"];

/**
 * UC4 steht in der Registry der Plattform nicht in `ucs`, sondern in `bereiche` (= `ucs` plus `einstieg`,
 * #98). Gesucht wird in `bereiche`, falls die Registry sie exportiert, sonst in `ucs`; so erscheint der
 * Link, sobald die Plattform den Eintrag führt, ohne dass die Landing vorher bricht.
 */
export function findeEinstieg(
  quelle: Record<string, unknown> = registry as unknown as Record<string, unknown>,
): { id: string; route: string } | undefined {
  const liste = (Array.isArray(quelle.bereiche) ? quelle.bereiche : quelle.ucs) as
    | readonly { id: string; route: string }[]
    | undefined;
  return liste?.find((b) => b.id === "uc4");
}

/**
 * Use Case 4 „Gemeinsamer Einstieg“ (Epic #95) als verdeckter Eintrag: geschwärzt wie eine
 * Hochrisiko-Akte, `<details>` deckt ihn auf (ohne JavaScript, Tastatur und Screenreader inklusive).
 * Der Link erscheint erst, wenn die Registry (shared/ui/src/ucs.ts) einen Eintrag uc4 führt (`findeEinstieg`).
 */
function UseCaseVier({ index }: { index: number }) {
  const t = USE_CASES.uc4;
  const eintrag = findeEinstieg();
  return (
    <li className={`${s.zeile} ${a.uc} ${a.ucVier}`} style={{ "--i": index } as CSSProperties}>
      <details className={a.akte}>
        <summary className={a.akteKopf}>
          <span className={a.ucName}>
            <span className={a.akteVerdeckt}>{t.verdeckt}</span>
            <span className={a.akteName}>{t.name}</span>
          </span>
          <span className={a.akteVorschau} aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <span className={a.akteSchalter} aria-hidden="true">
            <span className={a.akteAuf}>{t.aufdecken}</span>
            <span className={a.akteZu}>{t.zudecken}</span>
          </span>
        </summary>
        <div className={a.akteInhalt}>
          <p className={a.ucText}>{t.text}</p>
          <p className={a.akteBeispiel}>
            <span className={s.nurLeser}>{t.beispielLabel}: </span>
            {t.beispiel}
          </p>
          <p className={a.ucSchritte}>
            {t.schritte.map((schritt, k) => (
              <span key={schritt}>
                {k > 0 ? (
                  <span className={a.ucPfeil} aria-hidden="true">
                    {" → "}
                  </span>
                ) : null}
                {k > 0 ? <span className={s.nurLeser}>, </span> : null}
                {schritt}
              </span>
            ))}
          </p>
          {eintrag ? (
            <Link href={eintrag.route} className={a.knopfLinie}>
              {USE_CASES.oeffnen}
              <span className={s.nurLeser}> {t.name}</span>
            </Link>
          ) : (
            <p className={a.akteStatus}>{t.inArbeit}</p>
          )}
        </div>
      </details>
    </li>
  );
}

/** „Drei Use Cases, ein Kern“: aus der UC-Registry, UC3 hervorgehoben. */
export default function UseCases() {
  const eintraege = REIHENFOLGE.map((id) => ucs.find((uc) => uc.id === id)).filter(
    (uc): uc is (typeof ucs)[number] => uc !== undefined,
  );

  return (
    <section id="use-cases" className={s.abschnitt} aria-labelledby="use-cases-titel">
      <div className={s.rahmen}>
        <header className={s.kopf}>
          <h2 id="use-cases-titel" className={s.titel}>
            {USE_CASES.titel}
          </h2>
          <p className={s.einleitung}>{USE_CASES.einleitung}</p>
        </header>

        <Einblenden className={s.einblenden}>
          <ul className={a.ucListe}>
            {eintraege.map((uc, i) => {
              const text = USE_CASES.eintraege[uc.id];
              return (
                <li
                  key={uc.id}
                  className={`${s.zeile} ${a.uc}`}
                  data-bewertet={uc.bewertet ? "" : undefined}
                  style={{ "--i": i } as CSSProperties}
                >
                  <div className={a.ucKopf}>
                    <h3 className={a.ucName}>{uc.name}</h3>
                    {uc.bewertet ? <span className={a.plakette}>{USE_CASES.bewertet}</span> : null}
                  </div>
                  <div className={a.ucInhalt}>
                    <p className={a.ucText}>{text.text}</p>
                    <p className={a.ucSchritte}>
                      {text.schritte.map((schritt, k) => (
                        <span key={schritt}>
                          {k > 0 ? (
                            <span className={a.ucPfeil} aria-hidden="true">
                              {" → "}
                            </span>
                          ) : null}
                          {k > 0 ? <span className={s.nurLeser}>, </span> : null}
                          {schritt}
                        </span>
                      ))}
                    </p>
                  </div>
                  <Link href={uc.route} className={uc.bewertet ? a.knopfVoll : a.knopfLinie}>
                    {USE_CASES.oeffnen}
                    <span className={s.nurLeser}> {uc.name}</span>
                  </Link>
                </li>
              );
            })}
            <UseCaseVier index={eintraege.length} />
          </ul>
        </Einblenden>
      </div>
    </section>
  );
}
