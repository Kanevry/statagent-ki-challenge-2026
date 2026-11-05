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

/** Modell, mit dem die aktuelle Seite wirklich rechnet, wenn es von der globalen Einstellung abweicht. */
export interface SeitenModellWert {
  provider: string;
  modell?: string | null;
  /** Die Seite schickt diesen Anbieter selbst mit jeder Anfrage (Modellwahl auf /uc4); dann gilt er immer. */
  gewaehlt?: boolean;
}

export interface ShellWert {
  /** Aktueller Pfad, z. B. `/uc3/lauf`. */
  pfad: string;
  Verweis: Verweis;
  /** Öffnet die Protokoll-Schublade; außerhalb der Shell ohne Wirkung. */
  oeffneProtokoll: () => void;
  /** Setzt die Modell-Vorgabe der Seite für den Badge im Header (`null` löscht sie). */
  setzeSeitenModell: (wert: SeitenModellWert | null) => void;
}

const ShellKontext = createContext<ShellWert>({
  pfad: "/",
  Verweis: StandardVerweis,
  oeffneProtokoll: () => {},
  setzeSeitenModell: () => {},
});

export function ShellAnbieter({ wert, children }: { wert: ShellWert; children: ReactNode }) {
  return <ShellKontext.Provider value={wert}>{children}</ShellKontext.Provider>;
}

export function useShell(): ShellWert {
  return useContext(ShellKontext);
}

export { StandardVerweis };
