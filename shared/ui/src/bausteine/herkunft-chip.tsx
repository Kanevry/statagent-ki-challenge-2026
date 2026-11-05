"use client";

import { Fragment, useId, useState } from "react";
import { Knopf, Piktogramm, Status } from "../basis";
import { fokus, klassen } from "../basis/klassen";

export type HerkunftChipProps = {
  /** Die Abfrage, mit der die Zahl gerechnet wurde. Fehlt sie, zeigt der Chip die Herkunft ohne „Kopieren“. */
  sql?: string | null;
  /** Monat der Lieferung, z. B. „2025-03“. */
  lieferung?: string | null;
  /** Berichtsmonat der Zahl; weicht er von `lieferung` ab, ist die Zahl eine Revision aus einer späteren Lieferung. */
  monat?: string | null;
  /** Version des Regelsatzes (`meta.regel`), mit dem gerechnet wurde. */
  regelstand?: string | null;
  /** Kennung des Laufs, der die Zahl erzeugt hat; im Chip auf acht Zeichen gekürzt, offen voll. */
  lauf?: string | null;
  /** Tabelle der Rohdaten; Standard `roh.lieferung`. */
  quelle?: string;
  /** Weiterer Verweis, z. B. Fundstelle oder Regelstand. */
  verweis?: string | null;
  /** `vorlaeufig`: die Zahl kann sich mit einer späteren Lieferung noch ändern. */
  stand?: "endgueltig" | "vorlaeufig" | null;
  /** Wörtliches Zitat einer Rechtsquelle (UC1, z. B. „BPGG § 4“); ersetzt beim Öffnen die SQL-Ansicht. */
  zitat?: string | null;
  /** Fassungsstand des Zitats, z. B. „BGBl. I Nr. 12/2026“ oder ein Datum. */
  fassung?: string | null;
  className?: string;
};

type Kopie = "bereit" | "kopiert" | "fehler";

/** Länge, auf die der Chip eine Laufkennung (Hash) kürzt. */
const LAUF_KURZ = 8;

/**
 * Beleg einer Zahl: ruhiger Textlink „Beleg“ (bei Zitaten die Quelle) mit Datenbank- bzw. Dokument-Symbol;
 * Quelle, Zeitpunkt, Regelstand und Lauf stehen im Namen des Knopfs und aufgeklappt in den Angaben, dazu das SQL
 * mit „Kopieren“ (UI-Regie 05.11.: keine Pille an jeder Zahl).
 * Steht als Block neben der Zahl (nicht innerhalb eines `<p>`), weil der geöffnete Bereich ein `<pre>` enthält.
 * Ohne SQL zeigt der aufgeklappte Beleg nur Quelle, Lieferung, Lauf und Verweis, ohne Kopieren.
 */
export function HerkunftChip({
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
  className,
}: HerkunftChipProps) {
  const bereichId = useId();
  const [offen, setOffen] = useState(false);
  const [kopie, setKopie] = useState<Kopie>("bereit");

  const vorlaeufig = stand === "vorlaeufig";
  const revision = Boolean(monat && lieferung && monat !== lieferung);
  const zeitpunkt = revision ? `Monat ${monat} aus Lieferung ${lieferung}` : (lieferung ?? monat);
  const laufKurz = lauf && lauf.length > LAUF_KURZ ? lauf.slice(0, LAUF_KURZ) : lauf;
  const teile = [
    regelstand && `Regelstand ${regelstand}`,
    laufKurz && `Lauf ${laufKurz}`,
    vorlaeufig && "vorläufig",
  ].filter((teil): teil is string => Boolean(teil));
  const angaben = [
    zeitpunkt && (revision ? zeitpunkt : `Lieferung ${zeitpunkt}`),
    regelstand && `Regelstand ${regelstand}`,
    lauf && `Lauf ${lauf}`,
    verweis && `Verweis ${verweis}`,
    vorlaeufig && "vorläufiger Stand",
  ]
    .filter(Boolean)
    .join(" · ");

  async function kopieren() {
    if (!sql) return;
    try {
      // Ohne sichere Verbindung (http) fehlt die Zwischenablage; dann bleibt das Markieren von Hand.
      if (!navigator.clipboard) throw new Error("Zwischenablage nicht verfügbar");
      await navigator.clipboard.writeText(sql);
      setKopie("kopiert");
    } catch {
      setKopie("fehler");
    }
  }

  return (
    <div className={klassen("inline-flex max-w-full flex-col items-start gap-2", className)} data-baustein="herkunft">
      <button
        type="button"
        aria-expanded={offen}
        aria-controls={offen ? bereichId : undefined}
        onClick={() => {
          setOffen(!offen);
          setKopie("bereit");
        }}
        title={lauf && laufKurz !== lauf ? `Lauf ${lauf}` : undefined}
        className={klassen(
          "inline-flex items-center gap-1 text-left font-sans text-12 text-slate underline decoration-line underline-offset-4 hover:text-gruen hover:decoration-gruen",
          fokus,
        )}
      >
        <Piktogramm name={zitat ? "protokoll" : "datenbank"} groesse={12} className="shrink-0" />
        {/* Ruhig (UI-Regie 05.11.): sichtbar nur, was man zum Weiterklicken braucht. Tabelle, Lieferung, Regelstand
            und Lauf stehen aufgeklappt in den Angaben und für Screenreader hier. */}
        <span>{zitat ? quelle : "Beleg"}</span>
        {(() => {
          const rest = [zitat ? null : quelle, zeitpunkt, ...teile].filter(Boolean).join(", ");
          return rest ? <span className="sr-only">{`, ${rest}`}</span> : null;
        })()}
      </button>
      {offen && (
        <div id={bereichId} className="flex w-full flex-col gap-2 rounded-lg border border-line bg-white p-3">
          {angaben && <p className="font-sans text-12 text-slate">{angaben}</p>}
          {zitat ? (
            // Rechtsquelle (UC1): das Zitat wörtlich, darunter der Fassungsstand; kein Satz über eine Abfrage.
            <>
              <blockquote className="font-sans text-14 text-ink">{zitat}</blockquote>
              {fassung && <p className="font-sans text-12 text-slate">{`Stand: ${fassung}`}</p>}
            </>
          ) : sql ? (
            <>
              <pre className="max-w-full overflow-x-auto whitespace-pre-wrap font-mono text-12 text-ink">
                <code>{sql}</code>
              </pre>
              <div className="flex flex-wrap items-center gap-4">
                <Knopf art="sekundaer" onClick={kopieren}>
                  Kopieren
                </Knopf>
                <span aria-live="polite">
                  {kopie === "kopiert" && <Status art="ok">Kopiert</Status>}
                  {kopie === "fehler" && <Status art="fehler">Kopieren geht hier nicht. Bitte markieren.</Status>}
                </span>
              </div>
            </>
          ) : (
            <p className="font-sans text-12 text-slate">{`Für diese Zahl ist keine Abfrage hinterlegt, sie stammt aus ${quelle}.`}</p>
          )}
        </div>
      )}
    </div>
  );
}
