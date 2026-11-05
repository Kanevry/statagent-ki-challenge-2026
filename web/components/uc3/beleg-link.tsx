import type { ReactNode } from "react";
import { monatName } from "./monat";
import type { Beleg } from "./beleg";

// Beleg als ruhiger Textlink (UI-Regie, Version 1): ein Beleg je Aussage-Block statt einer Pille an jeder Zahl.
// Zu sieht man nur das Wort „Beleg“; offen stehen Tabelle, Lieferung, Regelstand, Lauf und die Abfrage. Mono-Schrift
// nur hier drin (SQL, Tabellenname, Hash). Native <details>: ohne JavaScript bedienbar, Tastatur und Screenreader
// inklusive. Nie in ein <p> setzen (details ist ein Block). Bleibt lokal, bis die UI-Regie den Baustein nach shared/ui hochzieht.

export type BelegLinkProps = Beleg & {
  /** Linktext; Standard „Beleg“. */
  text?: string;
  className?: string;
};

function zeile(wort: string, wert: ReactNode) {
  return (
    <div className="flex flex-wrap gap-x-2">
      <dt className="font-sans text-12 text-slate">{wort}</dt>
      <dd className="break-all font-mono text-12 text-ink">{wert}</dd>
    </div>
  );
}

export function BelegLink({
  sql,
  lieferung,
  monat,
  regelstand,
  lauf,
  quelle = "roh.lieferung",
  verweis,
  stand,
  zitat,
  fassung,
  text = "Beleg",
  className,
}: BelegLinkProps) {
  const revision = Boolean(monat && lieferung && monat !== lieferung);
  return (
    <details className={`group inline-block max-w-full align-baseline ${className ?? ""}`} data-baustein="herkunft">
      <summary className="inline-flex min-h-6 cursor-pointer list-none items-center font-sans text-14 text-slate underline decoration-line underline-offset-4 hover:text-ink hover:decoration-ink [&::-webkit-details-marker]:hidden">
        {text}
      </summary>
      <div className="mt-2 flex w-[min(100vw-3rem,40rem)] max-w-full flex-col gap-2 border border-line bg-paper p-3">
        <dl className="flex flex-col gap-1">
          {zeile("Tabelle", quelle)}
          {lieferung && zeile(revision ? "Monat" : "Lieferung", revision && monat ? `${monatName(monat)} aus Lieferung ${monatName(lieferung)}` : monatName(lieferung))}
          {regelstand && zeile("Regelstand", regelstand)}
          {lauf && zeile("Lauf", lauf)}
          {verweis && zeile("Verweis", verweis)}
          {stand === "vorlaeufig" && zeile("Stand", "vorläufig")}
          {fassung && zeile("Fassung", fassung)}
        </dl>
        {zitat && <blockquote className="font-sans text-14 text-ink">{zitat}</blockquote>}
        {sql && (
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words bg-white p-2 font-mono text-12 text-ink" tabIndex={0}>
            {sql}
          </pre>
        )}
      </div>
    </details>
  );
}

export type Stand = "veroeffentlicht" | "angehalten" | "vorlaeufig" | "freigegeben" | "offen" | "abgelehnt";

const STAND: Record<Stand, { wort: string; punkt: string }> = {
  veroeffentlicht: { wort: "veröffentlicht", punkt: "bg-slate" },
  angehalten: { wort: "angehalten", punkt: "bg-gelb" },
  vorlaeufig: { wort: "vorläufig", punkt: "bg-gelb" },
  freigegeben: { wort: "freigegeben", punkt: "bg-gruen" },
  offen: { wort: "wartet auf Freigabe", punkt: "bg-gelb" },
  abgelehnt: { wort: "abgelehnt", punkt: "bg-slate" },
};

/** Status als ein Wort mit Punkt (grau veröffentlicht, gelb angehalten, grün nur freigegeben). */
export function StandPunkt({ stand, wort, className }: { stand: Stand; wort?: string; className?: string }) {
  const s = STAND[stand];
  return (
    <span className={`inline-flex items-center gap-2 font-sans text-14 text-ink ${className ?? ""}`}>
      <span aria-hidden="true" className={`size-2 shrink-0 rounded-full ${s.punkt}`} />
      {wort ?? s.wort}
    </span>
  );
}
