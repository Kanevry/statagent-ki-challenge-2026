"use client";

import type { KeyboardEvent, Ref } from "react";
import { fokus, klassen } from "../basis/klassen";
import { Piktogramm } from "../basis/piktogramm";
import type { UcEintrag } from "../ucs";
import { StandardVerweis, type Verweis } from "./kontext";
import { ModellBadge } from "./modell-badge";
import { appTabs, istAktiv, marke } from "./navigation";

// App-Header (Pen-Frame nas8Y): links die Marke, in der Mitte die Tabs aus der Registry, rechts Modell-Badge und
// Protokoll-Knopf. Die Tabs sind Links (sie wechseln die Seite), daher `aria-current` statt ARIA-Tabs. Alle bleiben
// mit Tab erreichbar; Pfeil links/rechts, Pos1 und Ende springen zusätzlich zwischen ihnen.
// Ab 1400 px steht alles in einer Zeile (Frame 1440 × 64); die Marke gibt dort nach und bricht ihre zweite Zeile um.
// Darunter bricht der Header in mehrere Zeilen um.

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
  const kopfMarke = marke(pfad, ucs);
  return (
    <header ref={kopfRef} className="border-b border-line bg-white">
      <div className="flex min-h-16 flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-2 min-[1400px]:flex-nowrap min-[1400px]:px-6">
        <div className="flex min-w-0 flex-col gap-0.5" data-marke="">
          <p className="font-display text-20 font-bold text-navy">{kopfMarke.name}</p>
          <p className="font-sans text-12 text-slate">{kopfMarke.zeile}</p>
        </div>
        <nav aria-label="Bereiche" className="overflow-x-auto min-[1400px]:mr-auto min-[1400px]:shrink-0">
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
                      "inline-flex items-center gap-2 rounded-lg px-3.5 py-2 font-sans text-14",
                      aktiv ? "bg-gruen font-bold text-white" : "text-ink hover:bg-paper",
                      fokus,
                    )}
                  >
                    <span>{tab.label}</span>
                    {tab.bewertet && (
                      <span className="rounded bg-mint px-1.5 py-0.5 text-12 font-normal text-ink">bewertet</span>
                    )}
                  </Verweis>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="flex shrink-0 items-center gap-3">
          <ModellBadge quelle={modellQuelle} />
          {/* Natives <button>, weil der Fokus per Ref zurückkommen muss (Knopf reicht keinen Ref). */}
          <button
            ref={protokollKnopfRef}
            type="button"
            className={klassen(
              "inline-flex items-center gap-2 rounded-lg border border-line px-3 py-2 font-sans text-14 text-ink hover:bg-paper",
              fokus,
            )}
            onClick={onProtokoll}
            aria-expanded={protokollOffen}
            aria-controls={protokollOffen ? schubladeId : undefined}
            data-protokoll-knopf=""
          >
            <Piktogramm name="protokoll" />
            Protokoll
          </button>
        </div>
      </div>
    </header>
  );
}
