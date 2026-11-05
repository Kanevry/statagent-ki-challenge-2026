import type { HTMLAttributes, ReactNode } from "react";
import { klassen } from "./klassen";

export type AkzentArt = "beleg" | "ki" | "warnung" | "fehler";

const artKlassen: Record<AkzentArt, string> = {
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
 * Akzent als linke Farblinie (2 px): grün = Beleg, violett = KI, gelb = Warnung, rot = Fehler.
 * Die Linie trägt keine Bedeutung allein; der Inhalt sagt, was gilt (bei Bedarf mit `Status`).
 */
export function Akzent({ art, className, children, ...rest }: AkzentProps) {
  return (
    <div className={klassen("border-l-2 pl-4", artKlassen[art], className)} data-akzent={art} {...rest}>
      {children}
    </div>
  );
}
