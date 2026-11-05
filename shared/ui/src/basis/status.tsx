import type { HTMLAttributes, ReactNode } from "react";
import { klassen } from "./klassen";

export type StatusArt = "ok" | "warnung" | "fehler" | "info";

const standardWort: Record<StatusArt, string> = {
  ok: "In Ordnung",
  warnung: "Warnung",
  fehler: "Fehler",
  info: "Hinweis",
};

const artKlassen: Record<StatusArt, string> = {
  ok: "text-gruen",
  warnung: "text-warn-fg",
  fehler: "text-err-fg",
  info: "text-navy",
};

/** Kleine Linien-Symbole, 16 × 16, Farbe aus `currentColor`. */
function Symbol({ art }: { art: StatusArt }) {
  return (
    <svg
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className="size-4 shrink-0"
      data-status-symbol={art}
    >
      {art === "warnung" ? (
        <>
          <path d="M8 2.5 14 13.5H2Z" />
          <path d="M8 6.5v3" />
          <path d="M8 11.75h.01" />
        </>
      ) : (
        <>
          <circle cx="8" cy="8" r="6" />
          {art === "ok" && <path d="m5.25 8.25 1.9 1.9 3.6-4" />}
          {art === "fehler" && <path d="m5.75 5.75 4.5 4.5m0-4.5-4.5 4.5" />}
          {art === "info" && (
            <>
              <path d="M8 7.25v3.5" />
              <path d="M8 5.25h.01" />
            </>
          )}
        </>
      )}
    </svg>
  );
}

export type StatusProps = HTMLAttributes<HTMLSpanElement> & {
  art: StatusArt;
  /** Eigenes Wort statt des Standards. Leer fällt auf das Standardwort zurück: nie Symbol allein. */
  children?: ReactNode;
};

/** Status, immer Symbol und Wort, nie nur Farbe. */
export function Status({ art, className, children, ...rest }: StatusProps) {
  const wort = children === undefined || children === null || children === "" ? standardWort[art] : children;
  return (
    <span
      className={klassen("inline-flex items-center gap-2 font-sans text-14 font-medium", artKlassen[art], className)}
      {...rest}
    >
      <Symbol art={art} />
      <span>{wort}</span>
    </span>
  );
}
