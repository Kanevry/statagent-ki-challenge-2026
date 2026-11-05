"use client";

import { createContext, useContext, type AnchorHTMLAttributes, type ComponentType, type ReactNode } from "react";

/**
 * Link-Komponente der App. `@kic/ui` hängt nicht von Next ab; die App reicht `next/link` herein
 * (web/lib/plattform/shell-rahmen.tsx). Standard ist ein schlichtes `<a>`.
 */
export type VerweisProps = AnchorHTMLAttributes<HTMLAnchorElement> & { href: string; children?: ReactNode };
export type Verweis = ComponentType<VerweisProps>;

function StandardVerweis(props: VerweisProps) {
  return <a {...props} />;
}

export interface ShellWert {
  /** Aktueller Pfad, z. B. `/uc3/lauf`. */
  pfad: string;
  Verweis: Verweis;
  /** Öffnet die Protokoll-Schublade; außerhalb der Shell ohne Wirkung. */
  oeffneProtokoll: () => void;
}

const ShellKontext = createContext<ShellWert>({ pfad: "/", Verweis: StandardVerweis, oeffneProtokoll: () => {} });

export function ShellAnbieter({ wert, children }: { wert: ShellWert; children: ReactNode }) {
  return <ShellKontext.Provider value={wert}>{children}</ShellKontext.Provider>;
}

export function useShell(): ShellWert {
  return useContext(ShellKontext);
}

export { StandardVerweis };
