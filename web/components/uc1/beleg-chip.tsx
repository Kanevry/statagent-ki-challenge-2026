"use client";

// Belege laufen über den gemeinsamen `HerkunftChip` (Felder `zitat` und `fassung`, E0 !74), damit UC1 und UC3
// gleich aussehen (Lead-Entscheid, „ein Kern für alle drei“). Diese Datei hält nur die UC1-Props an einer Stelle.

import { HerkunftChip } from "@kic/ui/bausteine";

export type BelegChipProps = {
  /** Fundstelle, z. B. „BPGG § 4“ oder „Antrag PAL080, S. 2“. */
  quelle: string;
  /** Wortlaut der Quelle, ungekürzt. */
  zitat: string;
  /** Fassungsstand, schon lesbar („1. Jänner 2015“); fehlt er, steht keine Zeile „Stand“. */
  fassung?: string | null;
  className?: string;
};

/** Beleg einer Aussage: HerkunftChip mit Dokument-Symbol, „Zitat ansehen“, aufgeklappt Zitat und „Stand: …“. */
export function BelegChip({ quelle, zitat, fassung, className }: BelegChipProps) {
  return <HerkunftChip quelle={quelle} zitat={zitat} fassung={fassung ?? null} className={className} />;
}
