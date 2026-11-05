"use client";

import type { KeyboardEvent, Ref } from "react";
import { knopfKlassen } from "../basis/knopf";
import { fokus, klassen } from "../basis/klassen";
import type { UcEintrag } from "../ucs";
import { StandardVerweis, type Verweis } from "./kontext";
import { ModellBadge } from "./modell-badge";
import { appTabs, istAktiv } from "./navigation";

// App-Header (Pen-Frame nas8Y): Tabs aus der Registry links, Modell-Badge und Protokoll-Schalter rechts.
// Die Tabs sind Links (sie wechseln die Seite), daher `aria-current` statt ARIA-Tabs. Alle bleiben mit Tab
// erreichbar; Pfeil links/rechts, Pos1 und Ende springen zusätzlich zwischen ihnen.

export interface AppHeaderProps {
  pfad: string;
  protokollOffen: boolean;
  onProtokoll: () => void;
  /** ID der Schublade für `aria-controls`. */
  schubladeId: string;
  Verweis?: Verweis;
  ucs?: readonly UcEintrag[];
  modellQuelle?: string;
  /** Ref auf den Knopf „Protokoll“: die Shell gibt ihm beim Schließen der Schublade den Fokus zurück. */
  protokollKnopfRef?: Ref<HTMLButtonElement>;
  /** Ref auf `<header>`: die Schublade setzt unter seiner Unterkante an. */
  kopfRef?: Ref<HTMLElement>;
}

function springe(ereignis: KeyboardEvent<HTMLElement>) {
  const ziele: Record<string, (i: number, n: number) => number> = {
    ArrowRight: (i, n) => (i + 1) % n,
    ArrowLeft: (i, n) => (i - 1 + n) % n,
    Home: () => 0,
    End: (_i, n) => n - 1,
  };
  const ziel = ziele[ereignis.key];
  if (!ziel) return;
  const links = Array.from(ereignis.currentTarget.querySelectorAll<HTMLAnchorElement>("a[href]"));
  const jetzt = links.indexOf(document.activeElement as HTMLAnchorElement);
  if (jetzt < 0) return;
  ereignis.preventDefault();
  links[ziel(jetzt, links.length)]?.focus();
}

export function AppHeader({
  pfad,
  protokollOffen,
  onProtokoll,
  schubladeId,
  Verweis = StandardVerweis,
  ucs,
  modellQuelle,
  protokollKnopfRef,
  kopfRef,
}: AppHeaderProps) {
  const tabs = appTabs(ucs);
  return (
    <header ref={kopfRef} className="border-b border-line bg-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-2 md:px-8">
        <nav aria-label="Bereiche" className="-mx-2 overflow-x-auto">
          <ul className="flex items-center gap-1 whitespace-nowrap" onKeyDown={springe}>
            {tabs.map((tab) => {
              const aktiv = istAktiv(tab.href, pfad);
              return (
                <li key={tab.schluessel}>
                  <Verweis
                    href={tab.href}
                    aria-current={aktiv ? "page" : undefined}
                    data-tab={tab.schluessel}
                    className={klassen(
                      "inline-flex h-10 items-center gap-2 rounded px-2 font-sans text-14 border-b-2",
                      aktiv
                        ? "border-gruen font-semibold text-ink"
                        : "border-transparent text-slate hover:text-ink",
                      fokus,
                    )}
                  >
                    <span>{tab.label}</span>
                    {tab.bewertet && (
                      <span className="rounded border border-gruen px-1 text-12 font-medium text-gruen">bewertet</span>
                    )}
                  </Verweis>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="flex items-center gap-4">
          <ModellBadge quelle={modellQuelle} />
          {/* Natives <button> mit Knopf-Klassen, weil der Fokus per Ref zurückkommen muss (Knopf reicht keinen Ref). */}
          <button
            ref={protokollKnopfRef}
            type="button"
            className={knopfKlassen("sekundaer")}
            onClick={onProtokoll}
            aria-expanded={protokollOffen}
            aria-controls={protokollOffen ? schubladeId : undefined}
            data-protokoll-knopf=""
          >
            Protokoll
          </button>
        </div>
      </div>
    </header>
  );
}
