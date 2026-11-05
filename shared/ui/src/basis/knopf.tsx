import type { ButtonHTMLAttributes, ReactNode } from "react";
import { fokus, klassen } from "./klassen";

export type KnopfArt = "primaer" | "sekundaer";

const artKlassen: Record<KnopfArt, string> = {
  primaer: "bg-gruen text-white hover:bg-gruen/90",
  sekundaer: "border border-gruen text-gruen hover:bg-gruen-bg",
};

/**
 * Klassen eines Knopfs, für Links, die wie ein Knopf aussehen sollen (`<a className={knopfKlassen()}>`).
 * Je Screen höchstens eine primäre Aktion.
 */
export function knopfKlassen(art: KnopfArt = "primaer", className?: string): string {
  return klassen(
    "inline-flex h-10 items-center justify-center gap-2 rounded-lg px-4 font-sans text-14 font-semibold",
    "transition-colors disabled:cursor-not-allowed disabled:opacity-50",
    fokus,
    artKlassen[art],
    className,
  );
}

export type KnopfProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "autoFocus"> & {
  art?: KnopfArt;
  children: ReactNode;
};

/**
 * Knopf. Standard ist `type="button"`: ein Knopf in einem Formular sendet nur, wenn `type="submit"`
 * ausdrücklich gesetzt ist. So löst Enter in einem Textfeld (implizites Absenden über den ersten
 * Submit-Knopf des Formulars) keine Freigabe aus. `autoFocus` wird verworfen, auch wenn es ungetypt
 * hereinkommt: der Fokus springt nie von selbst auf eine Aktion.
 */
export function Knopf({ art = "primaer", type = "button", className, children, ...rest }: KnopfProps) {
  const { autoFocus: _verworfen, ...erlaubt } = rest as typeof rest & { autoFocus?: boolean };
  return (
    <button type={type} className={knopfKlassen(art, className)} {...erlaubt}>
      {children}
    </button>
  );
}
