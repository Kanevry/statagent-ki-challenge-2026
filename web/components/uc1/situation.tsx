"use client";

import { useId, type FormEvent } from "react";
import { Fliesstext, Knopf, Status } from "@kic/ui/basis";
import { MAX_TEXT } from "./antwort";
import { useLotse } from "./lotse-kontext";

// Eingabe der Situation (Pen-Frames KN6mU, ytfvF): Feld, Senden, Sprache, Einfache Sprache, Beispiele,
// Datenschutz-Satz. Sprach-Orb und Dokument-Upload gibt es noch nicht, deshalb stehen sie hier nicht.

export const SITUATION_FELD_ID = "uc1-situation";

export const BEISPIELE = [
  "Ich war drei Wochen im Spital und soll zur Reha.",
  "Mein Kind braucht eine Zahnspange.",
  "Ich möchte etwas für meine Gesundheit tun, was zahlt die Kasse?",
] as const;

const fokus = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen";

export function Situation() {
  const { entwurf, setEntwurf, einstellungen, setEinstellungen, erzaehlen, lage, aufnahme } = useLotse();
  const hinweisId = useId();
  const laedt = lage.art === "laden";

  function absenden(ereignis: FormEvent<HTMLFormElement>) {
    ereignis.preventDefault();
    if (laedt) return;
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
          readOnly={aufnahme !== null && laedt}
          aria-describedby={hinweisId}
          placeholder="Was ist los? Ein Satz reicht, zum Beispiel: „Ich war drei Wochen im Spital und soll zur Reha.“"
          className={`w-full resize-y rounded border border-slate bg-white p-4 font-sans text-16 text-ink placeholder:text-slate ${fokus}`}
        />
        <p id={hinweisId} className="font-sans text-12 text-slate">
          {`Höchstens ${MAX_TEXT} Zeichen. Rückfragen kommen nur, wenn etwas fehlt.`}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <Knopf type="submit" disabled={laedt}>
          {laedt ? "Der Lotse liest" : "Senden"}
        </Knopf>
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
              className={`inline-flex h-8 cursor-pointer items-center rounded px-3 font-sans text-14 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-gruen ${
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
        <label className="inline-flex cursor-pointer items-center gap-2 font-sans text-14 text-ink">
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
        Der Lotse nennt Leistungen und Wege und stellt keine Diagnose. Ihr Text geht an ein Sprachmodell und wird
        für diese Sitzung gespeichert. Schreiben Sie bitte keinen Namen und keine Versicherungsnummer hinein.
      </Fliesstext>
      {lage.art === "fehler" && !lage.replay && <Status art="fehler">{lage.meldung}</Status>}
    </form>
  );
}
