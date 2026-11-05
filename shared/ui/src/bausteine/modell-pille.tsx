import type { HTMLAttributes } from "react";
import { klassen } from "../basis/klassen";

// Modell-Pille (Pen-Frame CKCV4): Fläche Violett-hell, Punkt und Text in Violett. Violett heißt KI (Token-Regel),
// der Punkt ist statisch: kein Pulsieren, keine Animation. Der Modellname steht als Datum in Mono, das Übrige in Inter.
// Reine Darstellung ohne Zustand, damit sie auch in Server-Komponenten und in der Freigabe-Karte läuft.

export type ModellPilleProps = HTMLAttributes<HTMLSpanElement>;

export function ModellPille({ className, children, ...rest }: ModellPilleProps) {
  return (
    <span
      className={klassen(
        "inline-flex max-w-full flex-wrap items-center gap-x-2 gap-y-1 rounded-full bg-violett-bg px-2.5 py-1.5 font-sans text-12 text-violett",
        className,
      )}
      data-baustein="modell"
      {...rest}
    >
      <span aria-hidden="true" className="size-2 shrink-0 rounded-full bg-violett" />
      {children}
    </span>
  );
}
