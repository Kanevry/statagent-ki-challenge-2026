"use client";

import { useId, useState } from "react";
import { fokus, klassen } from "./klassen";
import { datumText, monatText, themaKurz, zitatText } from "./namen";
import type { Beleg } from "./typen";

// Herkunft-Chip für Presse-Belege (Pen QVMco). Der Baustein HerkunftChip aus @kic/ui ist auf Zahlen mit SQL gebaut
// (Lieferung, Regelstand, Abfrage); ein Presse-Beleg hat Medium, Monat, Titel, Seite und Zitat. Gleiche Optik
// (grüner Chip, Linie links im Aufklappbereich), eigener Inhalt. Zu: nur Medium und Monat. Auf: Titel, Datum,
// PDF-Seite und das Zitat, nie der Volltext (höchstens 300 Zeichen).

export function BelegChip({ beleg, themen = [] }: { beleg: Beleg; themen?: string[] }) {
  const bereichId = useId();
  const [offen, setOffen] = useState(false);
  const monat = monatText(beleg.monat ?? beleg.datum);
  const angaben = [beleg.datum && datumText(beleg.datum), beleg.pdf_seite != null && `Seite ${beleg.pdf_seite}`]
    .filter(Boolean)
    .join(", ");

  return (
    <div className="inline-flex max-w-full flex-col items-start gap-2" data-baustein="herkunft" data-beleg={beleg.beleg_id}>
      <button
        type="button"
        aria-expanded={offen}
        aria-controls={offen ? bereichId : undefined}
        onClick={() => setOffen(!offen)}
        className={klassen(
          "inline-flex flex-wrap items-center gap-x-2 gap-y-1 rounded-full bg-gruen-bg px-2 py-1 text-left font-sans text-12 font-semibold text-gruen hover:underline",
          fokus,
        )}
      >
        <span data-teil="medium">{beleg.medium}</span>
        {monat && <span className="font-mono" data-teil="monat">{monat}</span>}
        <span className="font-normal">{offen ? "Beleg schließen" : "Beleg ansehen"}</span>
      </button>
      {offen && (
        <div id={bereichId} className="flex w-full max-w-xl flex-col gap-1 border-l-2 border-gruen bg-white py-2 pl-4 pr-2" data-teil="beleg-offen">
          {beleg.titel && <p className="font-sans text-14 font-semibold text-ink">{beleg.titel}</p>}
          <p className="font-sans text-12 text-slate">{[beleg.medium, angaben].filter(Boolean).join(", ")}</p>
          <blockquote className="font-sans text-14 text-ink" data-teil="zitat">
            {`„${zitatText(beleg.zitat)}“`}
          </blockquote>
          {themen.length > 0 && (
            <p className="font-sans text-12 text-slate">{`Stützt: ${themen.map((t) => themaKurz(t)).join(", ")}`}</p>
          )}
        </div>
      )}
    </div>
  );
}
