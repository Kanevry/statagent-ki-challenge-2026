"use client";

import { useCallback, useId, useMemo, useState, type ReactNode } from "react";
import { fokus, klassen } from "../basis/klassen";
import type { UcEintrag, UcId } from "../ucs";
import { AppHeader } from "./header";
import { ShellAnbieter, StandardVerweis, type ShellWert, type Verweis } from "./kontext";
import { protokollUc, zeigtHeader } from "./navigation";
import { ProtokollSchublade } from "./protokoll-schublade";

export interface AppShellProps {
  /** Aktueller Pfad; die App reicht `usePathname()` herein. */
  pfad: string;
  Verweis?: Verweis;
  children: ReactNode;
  ucs?: readonly UcEintrag[];
  modellQuelle?: string;
  protokollQuelle?: (uc: UcId) => string;
}

/**
 * Shell der App: Header mit Tabs, Modell-Badge und Protokoll-Schublade. Auf `/` (Landing) nur der Kontext,
 * ohne Header, damit die Landingpage frei rendert.
 */
export function AppShell({ pfad, Verweis = StandardVerweis, children, ucs, modellQuelle, protokollQuelle }: AppShellProps) {
  const [offen, setOffen] = useState(false);
  const schubladeId = useId();
  const oeffneProtokoll = useCallback(() => setOffen(true), []);
  const schliesse = useCallback(() => setOffen(false), []);
  const wert = useMemo<ShellWert>(() => ({ pfad, Verweis, oeffneProtokoll }), [pfad, Verweis, oeffneProtokoll]);

  if (!zeigtHeader(pfad)) return <ShellAnbieter wert={wert}>{children}</ShellAnbieter>;

  return (
    <ShellAnbieter wert={wert}>
      <a
        href="#inhalt"
        className={klassen(
          "sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-white focus:px-4 focus:py-2",
          "font-sans text-14 text-ink",
          fokus,
        )}
      >
        Zum Inhalt
      </a>
      <AppHeader
        pfad={pfad}
        Verweis={Verweis}
        ucs={ucs}
        modellQuelle={modellQuelle}
        protokollOffen={offen}
        onProtokoll={() => setOffen((o) => !o)}
        schubladeId={schubladeId}
      />
      {children}
      {offen && (
        <ProtokollSchublade id={schubladeId} uc={protokollUc(pfad, ucs)} onSchliessen={schliesse} quelle={protokollQuelle} />
      )}
    </ShellAnbieter>
  );
}
