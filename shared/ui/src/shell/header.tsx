"use client";

import type { KeyboardEvent, Ref } from "react";
import { fokus, klassen } from "../basis/klassen";
import { Piktogramm } from "../basis/piktogramm";
import type { UcEintrag } from "../ucs";
import { StandardVerweis, type SeitenModellWert, type Verweis } from "./kontext";
import { ModellBadge } from "./modell-badge";
import { appTabs, istAktiv, marke } from "./navigation";

// App-Header (Pen-Frame nas8Y): links die Marke, in der Mitte die Tabs aus der Registry, rechts Modell-Badge und
// Protokoll-Knopf. Die Tabs sind Links (sie wechseln die Seite), daher `aria-current` statt ARIA-Tabs. Alle bleiben
// mit Tab erreichbar; Pfeil links/rechts, Pos1 und Ende springen zusätzlich zwischen ihnen.
// Die Kanten folgen `max-w-7xl` wie Unter-Navigation und Inhalt (Review !45). In diese 1216 px passen Tabs
// (gemessen ≈ 850 px) und Badge mit Knopf (≈ 370 px, mit „zuletzt“ ≈ 480 px) nicht neben die Marke, ohne sie zu
// zerdrücken. Daher zwei Zeilen: oben Marke links, Modell-Badge und Protokoll rechts; darunter die Tabs. Die
// DOM-Reihenfolge folgt der Ansicht, damit die Tab-Folge nicht springt. Unter 1400 px darf die rechte Gruppe
// schrumpfen und umbrechen, damit bei 390 px nichts waagrecht überläuft. Die Tabs brechen um statt zu scrollen
// (Abnahme #64: bei 390 px waren UC2, UC4 und Präsentation unsichtbar); schmal entfällt der Vorsatz „UC3 · “,
// so passen sie in zwei Zeilen.

export interface AppHeaderProps {
  pfad: string;
  protokollOffen: boolean;
  onProtokoll: () => void;
  /** ID der Schublade für `aria-controls`. */
  schubladeId: string;
  Verweis?: Verweis;
  ucs?: readonly UcEintrag[];
  modellQuelle?: string;
  /** Modell-Vorgabe der aktuellen Seite (`SeitenModell`), sonst die globale Einstellung. */
  seitenModell?: SeitenModellWert | null;
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
  seitenModell = null,
  protokollKnopfRef,
  kopfRef,
}: AppHeaderProps) {
  const tabs = appTabs(ucs);
  const kopfMarke = marke(pfad, ucs);
  return (
    <header ref={kopfRef} className="border-b border-line bg-white">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-1 px-4 pt-3 pb-1 md:px-8">
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
          <div className="flex min-w-0 flex-col gap-0.5" data-marke="">
            <p className="font-display text-20 font-bold text-navy">{kopfMarke.name}</p>
            <p className="font-sans text-12 text-slate">{kopfMarke.zeile}</p>
          </div>
          <div className="flex min-w-0 max-w-full flex-wrap items-center justify-end gap-3 min-[1400px]:shrink-0">
            <ModellBadge quelle={modellQuelle} vorgabe={seitenModell} />
            {/* Natives <button>, weil der Fokus per Ref zurückkommen muss (Knopf reicht keinen Ref). */}
            <button
              ref={protokollKnopfRef}
              type="button"
              className={klassen(
                "inline-flex min-h-11 items-center gap-2 rounded-lg border border-line px-3 py-2 font-sans text-14 text-ink hover:bg-paper",
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
        <nav aria-label="Bereiche" className="-mx-1 p-1">
          <ul className="flex flex-wrap items-center gap-1" onKeyDown={springe}>
            {tabs.map((tab) => {
              const aktiv = istAktiv(tab.href, pfad);
              return (
                <li key={tab.schluessel} className="whitespace-nowrap">
                  <Verweis
                    href={tab.href}
                    aria-current={aktiv ? "page" : undefined}
                    data-tab={tab.schluessel}
                    className={klassen(
                      "inline-flex min-h-11 items-center gap-2 rounded-lg px-3.5 py-2 font-sans text-14",
                      aktiv ? "bg-gruen font-bold text-white" : "text-ink hover:bg-paper",
                      fokus,
                    )}
                  >
                    <span>
                      {tab.kuerzel && <span className="max-sm:hidden">{tab.kuerzel}</span>}
                      {tab.name}
                    </span>
                    {tab.bewertet && (
                      <span className="rounded bg-mint px-1.5 py-0.5 text-12 font-normal text-ink">bewertet</span>
                    )}
                  </Verweis>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </header>
  );
}
