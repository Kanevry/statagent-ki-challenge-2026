"use client";

import { useId, type FormEvent, type ReactNode } from "react";
import { Fliesstext, Knopf, Status } from "@kic/ui/basis";
import { MAX_TEXT, tausender } from "./antwort";
import { useLotse } from "./lotse-kontext";

// Eingabe der Situation (Pen-Frames KN6mU, ytfvF): Feld, Senden, Sprache, Einfache Sprache, Beispiele,
// Datenschutz-Satz. Sprach-Orb und Dokument-Upload gibt es noch nicht, deshalb stehen sie hier nicht.

export const SITUATION_FELD_ID = "uc1-situation";

export const BEISPIELE = [
  "Meine Mutter kommt allein nicht mehr zurecht.",
  "Ich war drei Wochen im Spital und soll zur Reha.",
  "Mein Kind braucht eine Zahnspange.",
  "Ich möchte etwas für meine Gesundheit tun, was zahlt die Kasse?",
] as const;

const fokus = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen";
/** Gesperrt per aria-disabled statt disabled: der Knopf behält den Fokus, Screenreader hören „nicht verfügbar“. */
export const GESPERRT = "min-h-11 aria-disabled:cursor-not-allowed aria-disabled:opacity-50";
/** Tippziel mindestens 44 px (WCAG 2.5.5); `knopfKlassen` hat 40 px Höhe, min-h hebt sie an. */
export const TIPP = "min-h-11";

/** `zusatz`: weitere Aktion neben „Senden“, z. B. „Zurück zur Antwort“ beim Ändern. */
export function Situation({ zusatz }: { zusatz?: ReactNode } = {}) {
  const { entwurf, setEntwurf, einstellungen, setEinstellungen, erzaehlen, lage, spielt } = useLotse();
  const hinweisId = useId();
  const laedt = lage.art === "laden";
  // Während eine Aufnahme läuft, geht nichts live hinaus (sonst mit der aufgezeichneten Sitzung).
  const gesperrt = laedt || spielt;

  function absenden(ereignis: FormEvent<HTMLFormElement>) {
    ereignis.preventDefault();
    if (gesperrt) return;
    void erzaehlen(entwurf);
  }

  return (
    <form onSubmit={absenden} noValidate className="flex max-w-3xl flex-col gap-4" aria-busy={laedt}>
      <div className="flex flex-col gap-2">
        <label htmlFor={SITUATION_FELD_ID} className="font-sans text-14 font-semibold text-ink">
          Ihre Situation
        </label>
        <textarea
          id={SITUATION_FELD_ID}
          name="text"
          rows={4}
          maxLength={MAX_TEXT}
          value={entwurf}
          onChange={(e) => setEntwurf(e.target.value)}
          readOnly={spielt}
          aria-describedby={hinweisId}
          placeholder="Was ist los? Ein Satz reicht, zum Beispiel: „Ich war drei Wochen im Spital und soll zur Reha.“"
          className={`w-full resize-y rounded border border-slate bg-white p-4 font-sans text-16 text-ink placeholder:text-slate ${fokus}`}
        />
        <p id={hinweisId} className="font-sans text-12 text-slate">
          {`Höchstens ${tausender(MAX_TEXT)} Zeichen.`}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <Knopf type="submit" aria-disabled={gesperrt} className={GESPERRT}>
          {laedt ? "Der Lotse liest" : "Senden"}
        </Knopf>
        {zusatz}
        <fieldset className="flex items-center gap-1 rounded border border-line bg-white p-1">
          <legend className="sr-only">Sprache der Antwort</legend>
          {(
            [
              ["de", "Deutsch"],
              ["en", "English"],
            ] as const
          ).map(([wert, name]) => (
            <label
              key={wert}
              lang={wert}
              className={`inline-flex h-11 cursor-pointer items-center rounded px-3 font-sans text-14 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-gruen ${
                einstellungen.sprache === wert ? "bg-gruen-bg font-semibold text-gruen" : "text-slate"
              }`}
            >
              <input
                type="radio"
                name="sprache"
                value={wert}
                checked={einstellungen.sprache === wert}
                onChange={() => setEinstellungen({ ...einstellungen, sprache: wert })}
                className="sr-only"
              />
              {name}
            </label>
          ))}
        </fieldset>
        <label className="inline-flex min-h-11 cursor-pointer items-center gap-2 font-sans text-14 text-ink">
          <input
            type="checkbox"
            checked={einstellungen.einfach}
            onChange={(e) => setEinstellungen({ ...einstellungen, einfach: e.target.checked })}
            className={`size-4 accent-gruen ${fokus}`}
          />
          Einfache Sprache
        </label>
      </div>

      <div className="flex flex-col gap-2">
        <p className="font-sans text-14 font-semibold text-ink" id={`${hinweisId}-beispiele`}>
          Beispiele
        </p>
        <ul aria-labelledby={`${hinweisId}-beispiele`} className="flex flex-col border-t border-line">
          {BEISPIELE.map((satz) => (
            <li key={satz} className="border-b border-line">
              <button
                type="button"
                onClick={() => {
                  setEntwurf(satz);
                  document.getElementById(SITUATION_FELD_ID)?.focus();
                }}
                className={`w-full py-3 text-left font-sans text-14 text-ink hover:text-gruen ${fokus}`}
              >
                {satz}
              </button>
            </li>
          ))}
        </ul>
      </div>

      <Fliesstext groesse={12} ton="gedaempft">
        Ihr Text geht an ein Sprachmodell und wird für dieses Gespräch gespeichert. Geburtsdatum, Adresse und Telefonnummer blendet der Lotse vorher aus, Namen nicht. Die Versicherungsnummer tragen Sie erst selbst im Formular ein.
      </Fliesstext>
      {lage.art === "fehler" && !lage.replay && lage.ort === "situation" && <Status art="fehler">{lage.meldung}</Status>}
    </form>
  );
}
