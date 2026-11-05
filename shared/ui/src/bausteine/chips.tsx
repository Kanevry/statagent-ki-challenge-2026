import type { HTMLAttributes, ReactNode } from "react";
import { Status } from "../basis";
import { klassen } from "../basis/klassen";

export type ChipProps = Omit<HTMLAttributes<HTMLSpanElement>, "children"> & {
  /** Kurzes Wort oder kurzer Satz; leer fällt auf „Warnung“ bzw. „Fehler“ zurück. */
  children?: ReactNode;
};

/** Gelber Chip für Auffälligkeiten, immer Symbol und Wort. */
export function WarnChip({ children, className, ...rest }: ChipProps) {
  return (
    <span
      className={klassen("inline-flex items-center rounded-full bg-warn-bg px-2 py-1", className)}
      data-baustein="warnung"
      {...rest}
    >
      <Status art="warnung">{children}</Status>
    </span>
  );
}

/** Roter Chip für Fehler, immer Symbol und Wort. */
export function FehlerChip({ children, className, ...rest }: ChipProps) {
  return (
    <span
      className={klassen("inline-flex items-center rounded-full bg-err-bg px-2 py-1", className)}
      data-baustein="fehler"
      {...rest}
    >
      <Status art="fehler">{children}</Status>
    </span>
  );
}
