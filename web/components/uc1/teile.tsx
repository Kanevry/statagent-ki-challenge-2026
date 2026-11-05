"use client";

import { useId, useState } from "react";
import { Fliesstext, Ueberschrift } from "@kic/ui/basis";
import { ModellPille } from "@kic/ui/bausteine";
import { formatStand, quelleAnzeige, type Aussage, type WebAntwort } from "./antwort";

// Kleine Teile der UC1-Seiten, nur aus Token-Klassen und Bausteinen von @kic/ui.

const fokus = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen";

export const SCHRITTE = ["Situation", "Leistungen", "Antrag", "Stelle"] as const;

/** Schrittzeiger 1 Situation · 2 Leistungen · 3 Antrag · 4 Stelle; der aktuelle Schritt trägt aria-current. */
export function Schrittzeiger({ aktiv }: { aktiv: 1 | 2 | 3 | 4 }) {
  return (
    <ol aria-label="Ihre Schritte" className="flex flex-wrap gap-x-4 gap-y-1 font-sans text-14">
      {SCHRITTE.map((name, i) => {
        const nummer = i + 1;
        const jetzt = nummer === aktiv;
        return (
          <li
            key={name}
            aria-current={jetzt ? "step" : undefined}
            className={jetzt ? "border-b-2 border-gruen font-semibold text-ink" : "border-b-2 border-transparent text-slate"}
          >
            {`${nummer} ${name}`}
          </li>
        );
      })}
    </ol>
  );
}

/** Kopfzeile einer UC1-Seite: Titel, Unterzeile, darunter der Schrittzeiger. */
export function Kopf({ titel, unter, schritt }: { titel: string; unter: string; schritt: 1 | 2 | 3 | 4 }) {
  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Ueberschrift stufe={2} als="h1">
          {titel}
        </Ueberschrift>
        <Fliesstext ton="gedaempft">{unter}</Fliesstext>
      </div>
      <Schrittzeiger aktiv={schritt} />
    </div>
  );
}

/** KI-Kennzeichnung an jeder Antwort (AI Act Art. 50) mit dem Modell, das geantwortet hat. */
export function KiKennzeichnung({ antwort }: { antwort: Pick<WebAntwort, "modell" | "provider"> }) {
  if (!antwort.modell) {
    return <ModellPille data-testid="uc1-ki">Antwort vom Programm, ohne Sprachmodell</ModellPille>;
  }
  const modell = antwort.provider ? `${antwort.provider}, ${antwort.modell}` : antwort.modell;
  return <ModellPille data-testid="uc1-ki">{`Antwort von einer KI, geprüft gegen die Quellen (Modell ${modell})`}</ModellPille>;
}

/** „Beleg anzeigen“: zeigt das Zitat wörtlich, die Quelle und den Stand der Fassung. Mehr Text gibt es nicht. */
export function Beleg({ aussage }: { aussage: Aussage }) {
  const bereich = useId();
  const [offen, setOffen] = useState(false);
  const quelle = quelleAnzeige(aussage.quelle);
  return (
    <div className="flex max-w-full flex-col items-start gap-2" data-uc1-beleg="">
      <button
        type="button"
        aria-expanded={offen}
        aria-controls={offen ? bereich : undefined}
        onClick={() => setOffen(!offen)}
        className={`inline-flex min-h-8 items-center gap-1.5 rounded-full bg-gruen-bg px-2.5 py-1 text-left font-sans text-12 text-gruen hover:underline ${fokus}`}
      >
        <span>{offen ? "Beleg ausblenden" : "Beleg anzeigen"}</span>
        <span>{`(${quelle})`}</span>
      </button>
      {offen && (
        <figure id={bereich} className="flex flex-col gap-2 border-l-2 border-gruen bg-white py-2 pl-4 pr-2">
          <blockquote className="font-sans text-14 text-ink" data-uc1-zitat="">
            {`„${aussage.zitat}“`}
          </blockquote>
          <figcaption className="font-sans text-12 text-slate">
            {aussage.stand ? `${quelle}. Stand der Fassung: ${formatStand(aussage.stand)}` : quelle}
          </figcaption>
        </figure>
      )}
    </div>
  );
}
