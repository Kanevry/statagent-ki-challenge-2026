import type { HTMLAttributes, ReactNode } from "react";
import { klassen } from "./klassen";

type Stufe = 1 | 2 | 3;

const stufenKlassen: Record<Stufe, string> = {
  1: "text-56 font-bold",
  2: "text-32 font-bold",
  3: "text-20 font-bold",
};

export type UeberschriftProps = HTMLAttributes<HTMLHeadingElement> & {
  /** Optische Stufe: 1 = 56 px, 2 = 32 px, 3 = 20 px. */
  stufe: Stufe;
  /** Semantische Ebene, falls sie von der optischen Stufe abweicht. */
  als?: "h1" | "h2" | "h3" | "h4";
  children: ReactNode;
};

/** Überschrift in Space Grotesk. Als Aussage formulieren, nicht als Frage; keine Zeile darüber. */
export function Ueberschrift({ stufe, als, className, children, ...rest }: UeberschriftProps) {
  const Tag = als ?? (`h${stufe}` as const);
  return (
    <Tag className={klassen("font-display text-ink text-balance", stufenKlassen[stufe], className)} {...rest}>
      {children}
    </Tag>
  );
}

export type FliesstextProps = HTMLAttributes<HTMLParagraphElement> & {
  groesse?: 16 | 14 | 12;
  /** `gedaempft` für Nebentext in Slate. */
  ton?: "normal" | "gedaempft";
  children: ReactNode;
};

const groessenKlassen = { 16: "text-16", 14: "text-14", 12: "text-12" } as const;

/** Fließtext in Inter. */
export function Fliesstext({ groesse = 16, ton = "normal", className, children, ...rest }: FliesstextProps) {
  return (
    <p
      className={klassen(
        "font-sans text-pretty",
        groessenKlassen[groesse],
        ton === "gedaempft" ? "text-slate" : "text-ink",
        className,
      )}
      {...rest}
    >
      {children}
    </p>
  );
}

const zahlFormat = new Intl.NumberFormat("de-AT", { maximumFractionDigits: 2 });

export type ZahlProps = HTMLAttributes<HTMLSpanElement> & {
  /** Zahlen werden deutsch formatiert (1.234,5), Text bleibt wie geliefert. */
  wert: number | string;
  einheit?: string;
};

/** Zahl in JetBrains Mono mit Ziffern gleicher Breite, damit Spalten bündig stehen. */
export function Zahl({ wert, einheit, className, ...rest }: ZahlProps) {
  const text = typeof wert === "number" ? zahlFormat.format(wert) : wert;
  return (
    <span className={klassen("font-mono tabular-nums", className)} {...rest}>
      {einheit ? `${text} ${einheit}` : text}
    </span>
  );
}
