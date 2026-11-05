import type { HTMLAttributes } from "react";
import { klassen } from "../basis/klassen";

// Modell-Angabe: eine ruhige Zeile in Slate, ohne Fläche und ohne Punkt (UI-Regie 05.11.: eine Akzentfarbe, keine
// Pillen). Der Name bleibt `ModellPille`, damit alle Stellen sie weiter nutzen.
// Reine Darstellung ohne Zustand, damit sie auch in Server-Komponenten und in der Freigabe-Karte läuft.

export type ModellPilleProps = HTMLAttributes<HTMLSpanElement>;

export function ModellPille({ className, children, ...rest }: ModellPilleProps) {
  return (
    <span
      className={klassen(
        "inline-flex max-w-full flex-wrap items-center gap-x-1.5 gap-y-1 font-sans text-12 text-slate",
        className,
      )}
      data-baustein="modell"
      {...rest}
    >
      {children}
    </span>
  );
}
