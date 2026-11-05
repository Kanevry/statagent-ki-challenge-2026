"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, type FormEvent } from "react";
import { Akzent, Fliesstext, Knopf, knopfKlassen, Status, Ueberschrift } from "@kic/ui/basis";
import { jaNeinFrage, traegerName, type WebAntwort } from "./antwort";
import { antragLeistung, leistungName } from "./leistungen";
import { useLotse, type Lage, type Wechsel } from "./lotse-kontext";
import { GESPERRT } from "./situation";
import { AufnahmeHinweis, Beleg, KiKennzeichnung, KOPF_ID, MitTelefon } from "./teile";

// Antworten des Lotsen (Pen-Frame B1gvr): Rückfrage mit Schnellantworten, Leistungen mit „Antrag vorbereiten“, Aussagen mit Beleg,
// zuständige Stelle und nächste Schritte. Eine Einschätzung wie „sehr wahrscheinlich“ rechnet der Kern nicht,
// deshalb steht sie hier nicht.

const SCHNELL = ["Ja", "Nein", "Weiß nicht"] as const;

/** Feld der aktiven Rückfrage; nach einer neuen Rückfrage springt der Fokus dorthin. */
export const RUECKFRAGE_FELD_ID = "uc1-rueckfrage";

function Rueckfrage({ antwort, aktiv }: { antwort: WebAntwort; aktiv: boolean }) {
  const { antworten, antwortEntwurf, setAntwortEntwurf, lage, spielt } = useLotse();
  const frage = antwort.rueckfrage ?? antwort.text;
  const laedt = lage.art === "laden";
  // Während eine Aufnahme läuft, geht keine Antwort live hinaus (sonst mit der aufgezeichneten Sitzung).
  const gesperrt = laedt || spielt;
  const feldId = RUECKFRAGE_FELD_ID;
  const fehler = aktiv && lage.art === "fehler" && !lage.replay && lage.ort === "rueckfrage" ? lage.meldung : null;

  function absenden(ereignis: FormEvent<HTMLFormElement>) {
    ereignis.preventDefault();
    if (!gesperrt) void antworten(antwortEntwurf);
  }

  return (
    <Akzent art="ki" className="flex flex-col gap-4 bg-white py-4 pr-4">
      <Fliesstext className={aktiv ? "font-semibold md:text-20" : "font-semibold"}><MitTelefon text={frage} /></Fliesstext>
      {aktiv && (
        <form onSubmit={absenden} noValidate className="flex flex-col gap-4">
          {jaNeinFrage(frage) && (
            <div className="flex flex-wrap gap-2" role="group" aria-label="Schnellantwort">
              {SCHNELL.map((wort) => (
                <Knopf
                  key={wort}
                  art="sekundaer"
                  aria-disabled={gesperrt}
                  className={GESPERRT}
                  onClick={() => {
                    if (!gesperrt) void antworten(wort);
                  }}
                >
                  {wort}
                </Knopf>
              ))}
            </div>
          )}
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <div className="flex flex-1 flex-col gap-2">
              <label htmlFor={feldId} className="font-sans text-14 font-semibold text-ink">
                Ihre Antwort
              </label>
              <input
                id={feldId}
                value={antwortEntwurf}
                maxLength={1000}
                readOnly={spielt}
                aria-invalid={fehler ? true : undefined}
                onChange={(e) => setAntwortEntwurf(e.target.value)}
                className="h-11 rounded border border-slate bg-white px-4 font-sans text-16 text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen"
              />
            </div>
            <Knopf type="submit" aria-disabled={gesperrt} className={GESPERRT}>
              Antworten
            </Knopf>
          </div>
          {fehler && <Status art="fehler">{fehler}</Status>}
        </form>
      )}
    </Akzent>
  );
}

function AntragKnopf({ antwort }: { antwort: WebAntwort }) {
  const { antragVorbereiten, spielt } = useLotse();
  const router = useRouter();
  return (
    <div>
      <Knopf
        aria-disabled={spielt}
        className={GESPERRT}
        onClick={() => {
          if (spielt) return;
          void antragVorbereiten(antwort.antraege);
          router.push("/uc1/antrag");
        }}
      >
        Antrag vorbereiten
      </Knopf>
    </div>
  );
}

/** Leistungen, Aussagen mit Beleg und nächste Schritte. Die Überschrift „Das kommt für Sie in Frage“ trägt die Seite. */
function Ergebnis({ antwort, letzte }: { antwort: WebAntwort; letzte: boolean }) {
  const { aufgezeichnet } = useLotse();
  return (
    <div className="flex flex-col gap-6">
      {antwort.leistungen.length > 0 && (
        <ul className="flex flex-col gap-4" aria-label="Erkannte Leistungen">
          {antwort.leistungen.map((id) => {
            const stellen = antwort.traeger.filter((t) => !t.leistung || t.leistung === id);
            const art = antwort.antraege.find((a) => antragLeistung(a) === id);
            // Im Beispiel gibt es nur die aufgezeichneten Anträge; für die anderen steht ein ehrlicher Satz.
            const ohneAufnahme = art !== undefined && aufgezeichnet !== null && !aufgezeichnet.includes(art);
            return (
              <li key={id} data-uc1-leistung={id} className="flex flex-col gap-2 rounded border border-line bg-white p-4 md:p-6">
                <Ueberschrift stufe={3} als="h2">
                  {leistungName(id)}
                </Ueberschrift>
                {stellen.map((stelle) => (
                  <Fliesstext key={traegerName(stelle)} groesse={14}>
                    {`Zuständig: ${traegerName(stelle)}${stelle.fundstelle ? ` (${stelle.fundstelle})` : ""}.`}
                  </Fliesstext>
                ))}
                {art &&
                  (letzte && ohneAufnahme ? (
                    <Fliesstext groesse={14} ton="gedaempft" data-uc1-ohne-aufnahme={art}>
                      Dafür gibt es einen Antrag. Im Beispiel ist er nicht aufgezeichnet. Im echten Gespräch füllt der Lotse
                      ihn auch aus.
                    </Fliesstext>
                  ) : letzte ? (
                    <AntragKnopf antwort={antwort} />
                  ) : (
                    <Fliesstext groesse={14} ton="gedaempft">
                      Dafür gibt es einen Antrag.
                    </Fliesstext>
                  ))}
              </li>
            );
          })}
        </ul>
      )}

      {antwort.aussagen.length > 0 && (
        <section className="flex flex-col gap-4" aria-label="Was in den Quellen steht">
          <Ueberschrift stufe={3} als="h2">
            Was in den Quellen steht
          </Ueberschrift>
          <ul className="flex flex-col gap-4">
            {antwort.aussagen.map((aussage, i) => (
              <li key={`${aussage.quelle}-${i}`} className="flex flex-col items-start gap-2 border-b border-line pb-4">
                <Fliesstext><MitTelefon text={aussage.text} /></Fliesstext>
                {aussage.hinweis_hoehe && (
                  <Fliesstext groesse={14} ton="gedaempft">
                    Die genaue Höhe legt die zuständige Stelle fest.
                  </Fliesstext>
                )}
                <Beleg aussage={aussage} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {antwort.naechste_schritte.length > 0 && (
        <section className="flex flex-col gap-2" aria-label="So geht es weiter">
          <Ueberschrift stufe={3} als="h2">
            So geht es weiter
          </Ueberschrift>
          <ol className="flex list-decimal flex-col gap-1 pl-6 font-sans text-16 text-ink">
            {antwort.naechste_schritte.map((schritt) => (
              <li key={schritt}><MitTelefon text={schritt} /></li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

function AntwortBlock({ wechsel, letzte, onAendern }: { wechsel: Wechsel; letzte: boolean; onAendern?: () => void }) {
  const { antwort, eingabe } = wechsel;
  // Bei einer Antwort mit Aussagen stehen Text und Aussagen doppelt; dann zeigt die Seite die gegliederte Form.
  const zeigeText = antwort.verhalten !== "rueckfrage" && !(antwort.verhalten === "antwort" && antwort.aussagen.length > 0);
  return (
    <article className="flex flex-col gap-4" data-uc1-antwort={antwort.verhalten}>
      <Fliesstext groesse={14} ton="gedaempft">{`Sie: ${eingabe}`}</Fliesstext>
      {zeigeText && <Fliesstext className="whitespace-pre-line"><MitTelefon text={antwort.text} /></Fliesstext>}
      {antwort.verhalten === "rueckfrage" && <Rueckfrage antwort={antwort} aktiv={letzte} />}
      {antwort.verhalten === "uebergabe" && antwort.uebergabe_an && (
        <Akzent art="warnung">
          <Fliesstext className="font-semibold">Bitte wenden Sie sich an: <MitTelefon text={antwort.uebergabe_an} /></Fliesstext>
        </Akzent>
      )}
      {antwort.verhalten === "abstinenz" && letzte && (
        <div>
          {onAendern ? (
            <Knopf art="sekundaer" onClick={onAendern} className="min-h-11">
              Frage anders stellen
            </Knopf>
          ) : (
            <Link href="/uc1" className={knopfKlassen("sekundaer", "min-h-11")}>
              Frage anders stellen
            </Link>
          )}
        </div>
      )}
      {antwort.verhalten === "antwort" && <Ergebnis antwort={antwort} letzte={letzte} />}
      {antwort.hinweise.length > 0 && (
        <ul className="flex flex-col gap-1">
          {antwort.hinweise.map((hinweis) => (
            <li key={hinweis}>
              <Status art="info"><MitTelefon text={hinweis} /></Status>
            </li>
          ))}
        </ul>
      )}
      <div>
        <KiKennzeichnung antwort={antwort} />
      </div>
    </article>
  );
}

function ansage(lage: Lage, verlauf: readonly Wechsel[]): string {
  if (lage.art === "laden") return "Der Lotse liest Ihre Angaben.";
  if (lage.art === "fehler") return lage.meldung;
  const letzte = verlauf.at(-1)?.antwort;
  if (!letzte) return "";
  if (letzte.verhalten === "rueckfrage") return "Der Lotse hat eine Rückfrage.";
  return "Die Antwort ist da.";
}

/**
 * Setzt nach einer neuen Antwort den Fokus auf die neue Hauptaussage: bei einer Rückfrage auf das Antwortfeld,
 * sonst auf die Überschrift der Seite. Beim ersten Anzeigen (Seitenwechsel) bleibt der Fokus, wo er ist.
 */
function useFokusNachAntwort(verlauf: readonly Wechsel[], lage: Lage): void {
  const bekannt = useRef(verlauf.length);
  useEffect(() => {
    if (lage.art !== "bereit" || verlauf.length === bekannt.current) {
      bekannt.current = verlauf.length;
      return;
    }
    bekannt.current = verlauf.length;
    const rueckfrage = verlauf.at(-1)?.antwort.verhalten === "rueckfrage";
    // Ein Frame Pause: die Seite tauscht erst die Ansicht (Eingabe, Rückfrage, Ergebnis), dann gibt es das Ziel.
    const rahmen = requestAnimationFrame(() => {
      const ziel = (rueckfrage && document.getElementById(RUECKFRAGE_FELD_ID)) || document.getElementById(KOPF_ID);
      ziel?.focus();
    });
    return () => cancelAnimationFrame(rahmen);
  }, [verlauf, lage]);
}

export interface AntwortenProps {
  /** Ändern der Situation auf derselben Seite; fehlt es, führt „Frage anders stellen“ nach /uc1. */
  onAendern?: () => void;
  /** Fehler zur Situation hier zeigen, weil auf der Seite kein Situationsfeld steht. */
  situationFehler?: boolean;
}

/**
 * Verlauf mit Live-Region, Replay-Kennzeichnung und Fehler mit „Beispiel ansehen“. Hauptaussage ist die letzte
 * Antwort; frühere Schritte stehen eingeklappt unter „Bisheriges Gespräch“.
 */
export function Antworten({ onAendern, situationFehler = false }: AntwortenProps = {}) {
  const { verlauf, lage, aufnahme, beispielAbspielen } = useLotse();
  useFokusNachAntwort(verlauf, lage);
  const frueher = verlauf.slice(0, -1);
  const letzte = verlauf.at(-1);
  return (
    <section aria-label="Antworten des Lotsen" aria-busy={lage.art === "laden"} className="flex max-w-3xl flex-col gap-6">
      <p role="status" aria-live="polite" className="sr-only">
        {ansage(lage, verlauf)}
      </p>
      <AufnahmeHinweis aufnahme={aufnahme} />
      {lage.art === "fehler" && lage.replay && (
        <div className="flex flex-col items-start gap-4" data-testid="uc1-fehler">
          <Status art="fehler">{lage.meldung}</Status>
          <Fliesstext groesse={14} ton="gedaempft">
            Sie können sich ein aufgezeichnetes Beispiel ansehen.
          </Fliesstext>
          <Knopf art="sekundaer" className="min-h-11" onClick={() => void beispielAbspielen()}>
            Beispiel ansehen
          </Knopf>
        </div>
      )}
      {situationFehler && lage.art === "fehler" && !lage.replay && lage.ort === "situation" && (
        <div className="flex flex-col items-start gap-4" data-testid="uc1-fehler">
          <Status art="fehler">{lage.meldung}</Status>
          <Link href="/uc1" className={knopfKlassen("sekundaer", "min-h-11")}>
            Situation neu erzählen
          </Link>
        </div>
      )}
      {letzte && <AntwortBlock wechsel={letzte} letzte onAendern={onAendern} />}
      {verlauf.some((w) => w.antwort.verhalten === "antwort") && (
        <Fliesstext groesse={14} ton="gedaempft">
          Nicht beurteilt: Krankheiten, Behandlungen und Medikamente. Dafür sind Ärztin oder Arzt da.
        </Fliesstext>
      )}
      {frueher.length > 0 && (
        <details className="border-t border-line pt-4">
          <summary className="inline-flex min-h-11 cursor-pointer items-center font-sans text-14 font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen">
            Bisheriges Gespräch
          </summary>
          <div className="flex flex-col gap-6 pt-4">
            {frueher.map((wechsel, i) => (
              <AntwortBlock key={`${wechsel.antwort.sitzung_id}-${i}`} wechsel={wechsel} letzte={false} />
            ))}
          </div>
        </details>
      )}
    </section>
  );
}

/** Startet das Beispiel einmal, wenn die Seite mit ?beispiel=pflege geöffnet wird. */
export function BeispielStart({ aktiv }: { aktiv: boolean }) {
  const { beispielAbspielen } = useLotse();
  const gestartet = useRef(false);
  useEffect(() => {
    if (!aktiv || gestartet.current) return;
    gestartet.current = true;
    void beispielAbspielen();
  }, [aktiv, beispielAbspielen]);
  return null;
}
