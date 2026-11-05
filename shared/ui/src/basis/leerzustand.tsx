import type { ReactElement } from "react";
import { klassen } from "./klassen";

export type LeerzustandProps = {
  /** Genau ein Satz: was fehlt und warum. */
  satz: string;
  /** Genau eine Aktion, z. B. ein Knopf oder ein Link mit `knopfKlassen`. */
  aktion?: ReactElement;
  className?: string;
};

/** Leerzustand: ein Satz, eine Aktion. Ohne Symbol-Kachel und ohne Illustration. */
export function Leerzustand({ satz, aktion, className }: LeerzustandProps) {
  return (
    <div className={klassen("flex flex-col items-start gap-4 py-8", className)}>
      <p className="font-sans text-16 text-slate">{satz}</p>
      {aktion}
    </div>
  );
}
