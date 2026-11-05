"use client";

import { useEffect, useRef, type FormEvent } from "react";
import { Akzent, Fliesstext, Knopf, Status, Ueberschrift } from "@kic/ui/basis";
import { jaNeinFrage, traegerName, type WebAntwort } from "./antwort";
import { leistungName } from "./leistungen";
import { useLotse, type Lage, type Wechsel } from "./lotse-kontext";
import { SITUATION_FELD_ID } from "./situation";
import { Beleg, KiKennzeichnung } from "./teile";

// Antworten des Lotsen (Pen-Frame B1gvr): Rückfrage mit Schnellantworten, Leistungen, Aussagen mit Beleg,
// zuständige Stelle und nächste Schritte. Eine Einschätzung wie „sehr wahrscheinlich“ rechnet der Kern nicht,
// deshalb steht sie hier nicht.

const SCHNELL = ["Ja", "Nein", "Weiß nicht"] as const;

function Rueckfrage({ antwort, aktiv }: { antwort: WebAntwort; aktiv: boolean }) {
  const { antworten, antwortEntwurf, setAntwortEntwurf, lage, aufnahme } = useLotse();
  const frage = antwort.rueckfrage ?? antwort.text;
  const laedt = lage.art === "laden";
  const feldId = `uc1-rueckfrage-${antwort.sitzung_id}`;

  function absenden(ereignis: FormEvent<HTMLFormElement>) {
    ereignis.preventDefault();
    if (!laedt) void antworten(antwortEntwurf);
  }

  return (
    <Akzent art="ki" className="flex flex-col gap-4 bg-white py-4 pr-4">
      <Fliesstext className="font-semibold">{frage}</Fliesstext>
      {aktiv && (
        <form onSubmit={absenden} noValidate className="flex flex-col gap-4">
          {jaNeinFrage(frage) && (
            <div className="flex flex-wrap gap-2" role="group" aria-label="Schnellantwort">
              {SCHNELL.map((wort) => (
                <Knopf key={wort} art="sekundaer" disabled={laedt} onClick={() => void antworten(wort)}>
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
                readOnly={aufnahme !== null && laedt}
                onChange={(e) => setAntwortEntwurf(e.target.value)}
                className="h-10 rounded border border-slate bg-white px-4 font-sans text-16 text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen"
              />
            </div>
            <Knopf type="submit" disabled={laedt}>
              Antworten
            </Knopf>
          </div>
        </form>
      )}
    </Akzent>
  );
}

function Ergebnis({ antwort }: { antwort: WebAntwort }) {
  const anzahl = antwort.leistungen.length;
  return (
    <div className="flex flex-col gap-6">
      {anzahl > 0 && (
        <section aria-labelledby={`uc1-leistungen-${antwort.sitzung_id}`} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <Ueberschrift stufe={3} als="h2" id={`uc1-leistungen-${antwort.sitzung_id}`}>
              Das kommt für Sie in Frage
            </Ueberschrift>
            <Fliesstext groesse={14} ton="gedaempft">
              {`${anzahl === 1 ? "1 Leistung" : `${anzahl} Leistungen`} erkannt. Jede Angabe hat eine Quelle.`}
            </Fliesstext>
          </div>
          <ul className="flex flex-col gap-4">
            {antwort.leistungen.map((id) => {
              const stellen = antwort.traeger.filter((t) => !t.leistung || t.leistung === id);
              return (
                <li key={id} data-uc1-leistung={id} className="flex flex-col gap-2 rounded border border-line bg-white p-4 md:p-6">
                  <Ueberschrift stufe={3} als="h3">
                    {leistungName(id)}
                  </Ueberschrift>
                  {stellen.map((stelle) => (
                    <Fliesstext key={traegerName(stelle)} groesse={14}>
                      {`Zuständig: ${traegerName(stelle)}${stelle.fundstelle ? ` (${stelle.fundstelle})` : ""}.`}
                    </Fliesstext>
                  ))}
                  {antwort.antraege.includes(id) && (
                    <Fliesstext groesse={14} ton="gedaempft">
                      Dafür gibt es einen Antrag. Das Vorbereiten kommt mit dem nächsten Stand.
                    </Fliesstext>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {antwort.aussagen.length > 0 && (
        <section className="flex flex-col gap-4" aria-label="Was in den Quellen steht">
          <Ueberschrift stufe={3} als="h3">
            Was in den Quellen steht
          </Ueberschrift>
          <ul className="flex flex-col gap-4">
            {antwort.aussagen.map((aussage, i) => (
              <li key={`${aussage.quelle}-${i}`} className="flex flex-col items-start gap-2 border-b border-line pb-4">
                <Fliesstext>{aussage.text}</Fliesstext>
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
          <Ueberschrift stufe={3} als="h3">
            So geht es weiter
          </Ueberschrift>
          <ol className="flex list-decimal flex-col gap-1 pl-6 font-sans text-16 text-ink">
            {antwort.naechste_schritte.map((schritt) => (
              <li key={schritt}>{schritt}</li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

function AntwortBlock({ wechsel, letzte }: { wechsel: Wechsel; letzte: boolean }) {
  const { antwort, eingabe } = wechsel;
  // Bei einer Antwort mit Aussagen stehen Text und Aussagen doppelt; dann zeigt die Seite die gegliederte Form.
  const zeigeText = antwort.verhalten !== "rueckfrage" && !(antwort.verhalten === "antwort" && antwort.aussagen.length > 0);
  return (
    <article className="flex flex-col gap-4" data-uc1-antwort={antwort.verhalten}>
      <Fliesstext groesse={14} ton="gedaempft">{`Sie: ${eingabe}`}</Fliesstext>
      {zeigeText && <Fliesstext className="whitespace-pre-line">{antwort.text}</Fliesstext>}
      {antwort.verhalten === "rueckfrage" && <Rueckfrage antwort={antwort} aktiv={letzte} />}
      {antwort.verhalten === "uebergabe" && antwort.uebergabe_an && (
        <Akzent art="warnung">
          <Fliesstext className="font-semibold">{`Bitte wenden Sie sich an: ${antwort.uebergabe_an}`}</Fliesstext>
        </Akzent>
      )}
      {antwort.verhalten === "abstinenz" && letzte && (
        <div>
          <Knopf art="sekundaer" onClick={() => document.getElementById(SITUATION_FELD_ID)?.focus()}>
            Frage anders stellen
          </Knopf>
        </div>
      )}
      {antwort.verhalten === "antwort" && <Ergebnis antwort={antwort} />}
      {antwort.hinweise.length > 0 && (
        <ul className="flex flex-col gap-1">
          {antwort.hinweise.map((hinweis) => (
            <li key={hinweis}>
              <Status art="info">{hinweis}</Status>
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

/** Verlauf mit Live-Region, Replay-Kennzeichnung und Fehler mit „Beispiel ansehen“. */
export function Antworten() {
  const { verlauf, lage, aufnahme, beispielAbspielen } = useLotse();
  return (
    <section aria-label="Antworten des Lotsen" aria-busy={lage.art === "laden"} className="flex max-w-3xl flex-col gap-6">
      <p role="status" aria-live="polite" className="sr-only">
        {ansage(lage, verlauf)}
      </p>
      {aufnahme && (
        <Status art="info" data-testid="uc1-aufnahme">
          {`Aufgezeichnetes Beispiel vom ${aufnahme}, keine Live-Antwort`}
        </Status>
      )}
      {lage.art === "fehler" && lage.replay && (
        <div className="flex flex-col items-start gap-4" data-testid="uc1-fehler">
          <Status art="fehler">{lage.meldung}</Status>
          <Fliesstext groesse={14} ton="gedaempft">
            Sie können sich ein aufgezeichnetes Beispiel ansehen.
          </Fliesstext>
          <Knopf art="sekundaer" onClick={() => void beispielAbspielen()}>
            Beispiel ansehen
          </Knopf>
        </div>
      )}
      {verlauf.map((wechsel, i) => (
        <AntwortBlock key={`${wechsel.antwort.sitzung_id}-${i}`} wechsel={wechsel} letzte={i === verlauf.length - 1} />
      ))}
      {verlauf.some((w) => w.antwort.verhalten === "antwort") && (
        <Fliesstext groesse={14} ton="gedaempft">
          Nicht beurteilt: Krankheiten, Behandlungen und Medikamente. Dafür sind Ärztin oder Arzt da.
        </Fliesstext>
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

