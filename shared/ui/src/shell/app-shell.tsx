"use client";

import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { fokus, klassen } from "../basis/klassen";
import type { BereichId, UcEintrag } from "../ucs";
import { AppHeader } from "./header";
import { ShellAnbieter, StandardVerweis, type SeitenModellWert, type ShellWert, type Verweis } from "./kontext";
import { protokollUc, zeigtHeader } from "./navigation";
import { ProtokollSchublade } from "./protokoll-schublade";

export interface AppShellProps {
  /** Aktueller Pfad; die App reicht `usePathname()` herein. */
  pfad: string;
  Verweis?: Verweis;
  children: ReactNode;
  ucs?: readonly UcEintrag[];
  modellQuelle?: string;
  protokollQuelle?: (uc: BereichId) => string;
}

/**
 * Shell der App: Header mit Tabs, Modell-Badge und Protokoll-Schublade. Auf `/` (Landing) nur der Kontext,
 * ohne Header, damit die Landingpage frei rendert.
 *
 * Die Schublade ist modal: solange sie offen ist, sind Header und Inhalt `inert`; sie setzt unter dem Header
 * an, damit Badge und Knopf sichtbar bleiben. Beim Schließen geht der Fokus ausdrücklich an den Knopf
 * „Protokoll“ (Ref), nicht an `document.activeElement`: Safari fokussiert Buttons beim Klick nicht.
 */
export function AppShell({ pfad, Verweis = StandardVerweis, children, ucs, modellQuelle, protokollQuelle }: AppShellProps) {
  const [offen, setOffen] = useState(false);
  const [oben, setOben] = useState(0);
  const schubladeId = useId();
  const knopf = useRef<HTMLButtonElement>(null);
  const kopf = useRef<HTMLElement>(null);
  const warOffen = useRef(false);

  // Unterkante des Headers messen, solange die Schublade offen ist (der Header bricht schmal um).
  useLayoutEffect(() => {
    if (!offen) return;
    const miss = () => setOben(Math.max(0, kopf.current?.getBoundingClientRect().bottom ?? 0));
    miss();
    window.addEventListener("resize", miss);
    window.addEventListener("scroll", miss, { passive: true });
    return () => {
      window.removeEventListener("resize", miss);
      window.removeEventListener("scroll", miss);
    };
  }, [offen]);

  // Nach dem Schließen ist `inert` schon entfernt, erst dann ist der Knopf fokussierbar.
  useEffect(() => {
    if (warOffen.current && !offen) knopf.current?.focus();
    warOffen.current = offen;
  }, [offen]);

  const [seitenModell, setzeSeitenModell] = useState<SeitenModellWert | null>(null);
  const oeffneProtokoll = useCallback(() => setOffen(true), []);
  const schliesse = useCallback(() => setOffen(false), []);
  const wert = useMemo<ShellWert>(
    () => ({ pfad, Verweis, oeffneProtokoll, setzeSeitenModell }),
    [pfad, Verweis, oeffneProtokoll],
  );

  if (!zeigtHeader(pfad)) return <ShellAnbieter wert={wert}>{children}</ShellAnbieter>;

  return (
    <ShellAnbieter wert={wert}>
      <div inert={offen} data-shell-geruest="" className="flex flex-1 flex-col">
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
          seitenModell={seitenModell}
          protokollOffen={offen}
          onProtokoll={() => setOffen((o) => !o)}
          schubladeId={schubladeId}
          protokollKnopfRef={knopf}
          kopfRef={kopf}
        />
        {children}
      </div>
      {offen && (
        <ProtokollSchublade
          id={schubladeId}
          uc={protokollUc(pfad, ucs)}
          onSchliessen={schliesse}
          quelle={protokollQuelle}
          oben={oben}
        />
      )}
    </ShellAnbieter>
  );
}
