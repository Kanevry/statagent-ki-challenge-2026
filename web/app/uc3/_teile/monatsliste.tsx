"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { formatDifferenz, formatZahl } from "@kic/ui/bausteine";
import { StandPunkt } from "@/components/uc3/beleg-link";
import { monatName } from "@/components/uc3/monat";
import { laufPfad } from "@/components/uc3/navigation";
import type { Monatslauf } from "@/components/uc3/typen";
import { bestandJeMonat, zeitraumArtAus } from "@/components/uc3/zeitraum";

// Monatsliste (UI-Regie v1): Monat · Beschäftigungsverhältnisse · zum Vormonat · Stand. Der Monatsname führt zur
// Monatsseite (zugleich Qualitätsbericht); ein Beleg für die ganze Zeitreihe steht im Kopf. Stand
// steht nur bei Ausnahmen (angehalten, vorläufig); 22-mal „veröffentlicht“ wäre Lärm. Die Abrechnung
// (gelesen, nicht gezählt, ausgeschlossen) erscheint erst auf Wunsch.

export type Zeile = { monat: Monatslauf; vormonat: number | null; gehtAuf: boolean };

const kopf = "border-b border-ink py-2 pr-4 text-left align-bottom font-sans text-12 font-semibold text-slate";
const zelle = "py-3 pr-4 align-top font-sans text-14 text-ink";
const zahl = `${zelle} text-right tabular-nums`;
const link = "text-ink underline decoration-line underline-offset-4 hover:decoration-ink";

function Stand({ monat, gehtAuf }: { monat: Monatslauf; gehtAuf: boolean }) {
  if (!gehtAuf) return <StandPunkt stand="fehler" />;
  if (monat.angehalten) return <StandPunkt stand="angehalten" />;
  if (monat.ergebnisStand !== "endgueltig") return <StandPunkt stand="vorlaeufig" />;
  return null;
}

export function Monatsliste({
  zeilen,
  regelsatz,
  titel,
  rechts,
}: {
  zeilen: readonly Zeile[];
  regelsatz: string;
  titel: ReactNode;
  /** Regelsatz-Segment und Beleg der Zeitreihe, rechts in der Kopfzeile. */
  rechts?: ReactNode;
}) {
  const [abrechnung, setAbrechnung] = useState(false);
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
        {titel}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <button
            type="button"
            aria-pressed={abrechnung}
            onClick={() => setAbrechnung(!abrechnung)}
            className="inline-flex min-h-11 items-center font-sans text-14 text-slate underline decoration-line underline-offset-4 hover:text-ink"
          >
            {abrechnung ? "Abrechnung ausblenden" : "Abrechnung zeigen"}
          </button>
          {rechts}
        </div>
      </div>

      <table className="hidden w-full border-collapse md:table">
        <caption className="sr-only">{bestandJeMonat(zeitraumArtAus(zeilen[0]?.monat.zeitraumArt))}</caption>
        <thead>
          <tr>
            <th scope="col" className={kopf}>Monat</th>
            <th scope="col" className={`${kopf} text-right`}>Beschäftigungs&shy;verhältnisse</th>
            <th scope="col" className={`${kopf} text-right`}>zum Vormonat</th>
            {abrechnung && (
              <>
                <th scope="col" className={`${kopf} text-right`}>Zeilen gelesen</th>
                <th scope="col" className={`${kopf} text-right`}>nicht gezählt</th>
                <th scope="col" className={`${kopf} text-right`}>ausgeschlossen</th>
              </>
            )}
            <th scope="col" className={`${kopf} pr-0`}>Stand</th>
          </tr>
        </thead>
        <tbody>
          {zeilen.map(({ monat, vormonat, gehtAuf }) => (
            <tr key={monat.lieferung} className="border-b border-line" data-lieferung={monat.lieferung}>
              <th scope="row" className={`${zelle} text-left font-medium`}>
                <Link href={laufPfad(monat.lieferung, regelsatz)} className={link}>
                  {monatName(monat.lieferung)}
                </Link>
              </th>
              <td className={zahl}>{formatZahl(monat.gezaehlt)}</td>
              <td className={zahl}>{vormonat === null ? <span className="text-slate">erster Monat</span> : formatDifferenz(monat.gezaehlt - vormonat)}</td>
              {abrechnung && (
                <>
                  <td className={zahl}>{formatZahl(monat.gelesen)}</td>
                  <td className={zahl}>{formatZahl(monat.nichtGezaehlt)}</td>
                  <td className={zahl}>{formatZahl(monat.ausgeschlossen)}</td>
                </>
              )}
              <td className={`${zelle} pr-0`}>
                <Stand monat={monat} gehtAuf={gehtAuf} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul className="flex flex-col md:hidden" aria-label="Monate">
        {zeilen.map(({ monat, vormonat, gehtAuf }) => (
          <li key={monat.lieferung} className="flex flex-col gap-1 border-b border-line py-3" data-lieferung={monat.lieferung}>
            <div className="flex items-baseline justify-between gap-4">
              <Link href={laufPfad(monat.lieferung, regelsatz)} className={`font-sans text-16 font-medium ${link}`}>
                {monatName(monat.lieferung)}
              </Link>
              <span className="font-sans text-16 tabular-nums text-ink">{formatZahl(monat.gezaehlt)}</span>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 font-sans text-14 text-slate">
              <span className="tabular-nums">{vormonat === null ? "erster Monat" : `${formatDifferenz(monat.gezaehlt - vormonat)} zum Vormonat`}</span>
              <Stand monat={monat} gehtAuf={gehtAuf} />
            </div>
            {abrechnung && (
              <p className="font-sans text-12 tabular-nums text-slate">
                {`${formatZahl(monat.gelesen)} Zeilen gelesen, ${formatZahl(monat.nichtGezaehlt)} nicht gezählt, ${formatZahl(monat.ausgeschlossen)} ausgeschlossen`}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
