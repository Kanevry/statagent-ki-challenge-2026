"use client";

import { useId, useState } from "react";
import { fokus, klassen } from "../basis/klassen";
import { GLOSSAR, type GlossarWort } from "./glossar";

// Begriffe aus dem Glossar brauchen keine Erklärung; für jeden anderen Begriff ist sie Pflicht.
export type BegriffProps = ({ wort: GlossarWort; erklaerung?: string } | { wort: string; erklaerung: string }) & {
  /** Erklärung immer sichtbar als Untertitel unter dem Begriff statt auf Nachfrage. */
  untertitel?: boolean;
  className?: string;
};

/**
 * Fachbegriff mit Erklärung in Alltagssprache. Standard: auf Nachfrage per Klick, Enter oder Leertaste,
 * Escape schließt. Mit `untertitel` steht die Erklärung dauerhaft darunter.
 */
export function Begriff({ wort, erklaerung, untertitel = false, className }: BegriffProps) {
  const erklaerungId = useId();
  const [offen, setOffen] = useState(false);
  const text = erklaerung ?? (GLOSSAR as Record<string, string>)[wort] ?? "";

  if (untertitel) {
    return (
      <span className={klassen("inline-flex flex-col", className)} data-baustein="begriff">
        <span>{wort}</span>
        <span className="font-sans text-12 font-normal text-slate">{text}</span>
      </span>
    );
  }

  return (
    <span className={className} data-baustein="begriff">
      <button
        type="button"
        aria-expanded={offen}
        aria-controls={offen ? erklaerungId : undefined}
        onClick={() => setOffen(!offen)}
        onKeyDown={(e) => {
          if (e.key === "Escape" && offen) setOffen(false);
        }}
        className={klassen(
          "cursor-help underline decoration-slate decoration-dotted underline-offset-4",
          fokus,
        )}
      >
        {wort}
      </button>
      {offen && (
        <span id={erklaerungId} role="note" className="font-sans text-14 text-slate">
          {` (${text})`}
        </span>
      )}
    </span>
  );
}
