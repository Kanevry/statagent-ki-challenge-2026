import type { HTMLAttributes, ReactNode } from "react";
import { klassen } from "./klassen";

export type AkzentArt = "beleg" | "ki" | "warnung" | "fehler";

export const artKlassen: Record<AkzentArt, string> = {
  beleg: "border-gruen",
  ki: "border-violett",
  warnung: "border-gelb",
  fehler: "border-err-fg",
};

export type AkzentProps = HTMLAttributes<HTMLDivElement> & {
  art: AkzentArt;
  children: ReactNode;
};

/**
 * Akzent: ein ruhiger Block ohne farbige Seitenlinie (UI-Regie 05.11.: farbige Seitenbalken sind eine Schablone).
 * Die Art bleibt als Datenattribut; der Inhalt sagt, was gilt (bei Bedarf mit `Status`). `artKlassen` bleibt für
 * Stellen, die die Farbe bewusst als Text- oder Randfarbe brauchen.
 */
export function Akzent({ art, className, children, ...rest }: AkzentProps) {
  return (
    <div className={klassen("flex flex-col gap-1", className)} data-akzent={art} {...rest}>
      {children}
    </div>
  );
}
