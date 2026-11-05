"use client";

import { useId, useState } from "react";
import { Knopf, Status } from "../basis";
import { fokus, klassen } from "../basis/klassen";

export type HerkunftChipProps = {
  /** Die Abfrage, mit der die Zahl gerechnet wurde. */
  sql: string;
  /** Monat der Lieferung, z. B. „2025-03“. */
  lieferung: string;
  /** Kennung des Laufs, der die Zahl erzeugt hat. */
  lauf?: string;
  /** Tabelle der Rohdaten; Standard `roh.lieferung`. */
  quelle?: string;
  className?: string;
};

type Kopie = "bereit" | "kopiert" | "fehler";

/**
 * Beleg einer Zahl: grüner Chip, der beim Öffnen Lauf und SQL zeigt, mit Knopf „Kopieren“.
 * Steht als Block neben der Zahl (nicht innerhalb eines `<p>`), weil der geöffnete Bereich ein `<pre>` enthält.
 */
export function HerkunftChip({ sql, lieferung, lauf, quelle = "roh.lieferung", className }: HerkunftChipProps) {
  const bereichId = useId();
  const [offen, setOffen] = useState(false);
  const [kopie, setKopie] = useState<Kopie>("bereit");

  async function kopieren() {
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
        className={klassen(
          "inline-flex items-center gap-2 rounded-full bg-gruen-bg px-2 py-1 font-sans text-12 font-semibold text-gruen hover:underline",
          fokus,
        )}
      >
        <span className="font-mono">{`${quelle} ${lieferung}`}</span>
        {" · "}
        <span>SQL ansehen</span>
      </button>
      {offen && (
        <div id={bereichId} className="flex w-full flex-col gap-2 border-l-2 border-gruen bg-white py-2 pl-4 pr-2">
          <p className="font-sans text-12 text-slate">
            {`Lieferung ${lieferung}`}
            {lauf ? ` · Lauf ${lauf}` : ""}
          </p>
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
        </div>
      )}
    </div>
  );
}
