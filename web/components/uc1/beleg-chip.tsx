"use client";

// Übergang: BelegChip hat dieselbe Optik, Bedienung und Wörter wie `HerkunftChip` mit Zitat (Felder `zitat` und
// `fassung`, E0 !74, auf main gemergt, in diesem Branch noch nicht). Sobald main eingemischt ist, steigt UC1 auf
// HerkunftChip um (nur Import-Tausch) und diese Datei fällt weg.

import { useId, useState } from "react";
import { Piktogramm } from "@kic/ui/basis";

const fokus = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen";

/** Dieselben Props wie die Zitat-Felder von `HerkunftChip`; der Umstieg ist dann nur ein Import-Tausch. */
export type BelegChipProps = {
  /** Fundstelle, z. B. „BPGG § 4“ oder „Antrag PAL080, S. 2“. */
  quelle: string;
  /** Wortlaut der Quelle, ungekürzt. */
  zitat: string;
  /** Fassungsstand, schon lesbar („1. Jänner 2015“); fehlt er, steht keine Zeile „Stand“. */
  fassung?: string | null;
  className?: string;
};

/**
 * Grüne Pille mit Dokument-Symbol, Quelle in Mono und „Zitat ansehen“. Aufgeklappt stehen das Zitat wörtlich und,
 * wenn bekannt, „Stand: …“. Auf dem Handy ist die Pille mindestens 44 px hoch (HerkunftChip noch nicht, Hinweis an E0).
 */
export function BelegChip({ quelle, zitat, fassung, className }: BelegChipProps) {
  const bereichId = useId();
  const [offen, setOffen] = useState(false);
  return (
    <div
      className={`inline-flex max-w-full flex-col items-start gap-2 ${className ?? ""}`}
      data-baustein="herkunft"
      data-uc1-beleg=""
    >
      <button
        type="button"
        aria-expanded={offen}
        aria-controls={offen ? bereichId : undefined}
        onClick={() => setOffen(!offen)}
        className={`inline-flex min-h-11 flex-wrap items-center gap-x-1.5 gap-y-1 rounded-full bg-gruen-bg px-2.5 py-1 text-left font-sans text-12 font-normal text-gruen hover:underline md:min-h-0 ${fokus}`}
      >
        <Piktogramm name="protokoll" groesse={12} className="shrink-0" />
        <span className="font-mono">{quelle}</span>
        {" · "}
        <span>Zitat ansehen</span>
      </button>
      {offen && (
        <div id={bereichId} className="flex w-full flex-col gap-2 border-l-2 border-gruen bg-white py-2 pl-4 pr-2">
          <blockquote className="border-l-2 border-line pl-3 font-sans text-14 text-ink" data-uc1-zitat="">
            {zitat}
          </blockquote>
          {fassung && <p className="font-sans text-12 text-slate">{`Stand: ${fassung}`}</p>}
        </div>
      )}
    </div>
  );
}
