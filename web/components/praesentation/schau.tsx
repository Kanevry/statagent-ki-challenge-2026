"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Knopf } from "@kic/ui/basis";
import { naechsteFolie, schalterFuerTaste } from "../../lib/praesentation/navigation";
import { BUEHNE, BUEHNE_BREITE, BUEHNE_HOEHE } from "./buehne-klassen";

/** Eine Folie, wie die Schau sie braucht: Beschriftung für die Leiste und fertig gebaute Teile vom Server. */
export interface SchauFolie {
  id: string;
  titel: string;
  /** Anfang der Zeitangabe, z. B. `3:15` */
  zeit?: string;
  /** Zeitangabe zum Lesen, z. B. `3:15 bis 4:15` */
  zeitText?: string;
  inhalt: ReactNode;
  /** `null`, wenn die Folie keinen Sprechtext hat */
  notizen: ReactNode | null;
}

/** Tasten, die in Formularen und auf Bedienelementen ihre eigene Aufgabe haben. */
function gehoertDemElement(ziel: EventTarget | null, taste: string): boolean {
  if (!(ziel instanceof HTMLElement)) return false;
  if (ziel.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(ziel.tagName)) return true;
  return taste === " " && ["BUTTON", "A", "SUMMARY"].includes(ziel.tagName);
}

const FOKUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen";

export function Schau({ folien, start }: { folien: SchauFolie[]; start: number }) {
  const anzahl = folien.length;
  const [nr, setNr] = useState(start);
  const [notizenAn, setNotizenAn] = useState(false);
  const [vollbild, setVollbild] = useState(false);
  const [kannVollbild, setKannVollbild] = useState(true);
  const [skala, setSkala] = useState(0.5);
  const wurzel = useRef<HTMLDivElement>(null);
  const platz = useRef<HTMLDivElement>(null);
  const folie = folien[nr - 1] ?? folien[0];

  const gehe = useCallback((ziel: number) => {
    setNr(ziel);
    const adresse = new URL(window.location.href);
    adresse.searchParams.set("folie", String(ziel));
    window.history.replaceState(null, "", adresse);
  }, []);

  const schalteVollbild = useCallback(() => {
    if (document.fullscreenElement) void document.exitFullscreen().catch(() => {});
    else void wurzel.current?.requestFullscreen().catch(() => {});
  }, []);

  useEffect(() => {
    setKannVollbild(document.fullscreenEnabled);
    const beiWechsel = () => setVollbild(document.fullscreenElement === wurzel.current);
    document.addEventListener("fullscreenchange", beiWechsel);
    return () => document.removeEventListener("fullscreenchange", beiWechsel);
  }, []);

  useEffect(() => {
    const beiTaste = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || gehoertDemElement(e.target, e.key)) return;
      const ziel = naechsteFolie(nr, anzahl, e.key);
      if (ziel !== null) {
        e.preventDefault();
        if (ziel !== nr) gehe(ziel);
        return;
      }
      const schalter = schalterFuerTaste(e.key);
      if (schalter === "notizen") setNotizenAn((an) => !an);
      else if (schalter === "vollbild") schalteVollbild();
    };
    window.addEventListener("keydown", beiTaste);
    return () => window.removeEventListener("keydown", beiTaste);
  }, [nr, anzahl, gehe, schalteVollbild]);

  // Die Bühne ist immer 1920 × 1080 und wird auf den freien Platz verkleinert. Im Fenster zählt die Breite, im Vollbild auch die Höhe.
  useLayoutEffect(() => {
    const el = platz.current;
    if (!el) return;
    const messen = () => {
      const { width, height } = el.getBoundingClientRect();
      const s = vollbild ? Math.min(width / BUEHNE_BREITE, height / BUEHNE_HOEHE) : width / BUEHNE_BREITE;
      if (s > 0) setSkala(s);
    };
    messen();
    const beobachter = new ResizeObserver(messen);
    beobachter.observe(el);
    return () => beobachter.disconnect();
  }, [vollbild]);

  if (!folie) return null;
  const zeitZeile = folie.zeitText ? ` (${folie.zeitText})` : "";

  return (
    <div
      ref={wurzel}
      data-vollbild={vollbild ? "an" : "aus"}
      className={`flex min-h-0 flex-1 ${vollbild ? `h-dvh flex-col gap-4 p-4 ${BUEHNE.grund}` : ""}`}
    >
      <nav
        aria-label="Folien"
        className={`${vollbild ? "hidden" : "hidden lg:flex"} w-[300px] shrink-0 flex-col gap-1 overflow-y-auto border-r border-line bg-white p-4`}
      >
        <p className="font-display text-16 font-bold text-ink">Folien</p>
        <p className="mb-3 font-sans text-12 text-slate">Pfeiltasten wechseln die Folie.</p>
        <ol className="flex flex-col">
          {folien.map((f, i) => (
            <li key={f.id} className="border-b border-line">
              <button
                type="button"
                onClick={() => gehe(i + 1)}
                aria-current={i + 1 === nr ? "step" : undefined}
                className={`flex w-full items-baseline gap-[10px] px-[10px] py-2 text-left font-sans text-13 ${FOKUS} ${
                  i + 1 === nr ? "bg-gruen-bg font-bold text-ink" : "text-ink hover:bg-paper"
                }`}
              >
                <span className={`w-10 shrink-0 font-mono text-12 tabular-nums ${i + 1 === nr ? "text-gruen" : "text-slate"}`}>
                  {f.zeit ?? i + 1}
                </span>
                <span>{f.titel}</span>
              </button>
            </li>
          ))}
        </ol>
        <p className="mt-auto pt-4 font-sans text-12 text-slate">Pfeiltasten: Folie. F: Vollbild. N: Notizen.</p>
      </nav>

      <div className={`flex min-w-0 flex-1 flex-col gap-4 ${vollbild ? "min-h-0" : "p-4 md:p-6"}`}>
        <div ref={platz} className={vollbild ? "flex min-h-0 flex-1 items-center justify-center" : "w-full"}>
          <section
            aria-roledescription="Folie"
            aria-label={`Folie ${nr} von ${anzahl}: ${folie.titel}`}
            data-folie={nr}
            data-folie-id={folie.id}
            style={{ width: BUEHNE_BREITE * skala, height: BUEHNE_HOEHE * skala }}
            className={`relative shrink-0 overflow-hidden ${BUEHNE.grund}`}
          >
            <div
              style={{ width: BUEHNE_BREITE, height: BUEHNE_HOEHE, transform: `scale(${skala})`, transformOrigin: "top left" }}
              className="absolute left-0 top-0"
            >
              {folie.inhalt}
            </div>
          </section>
        </div>

        <p role="status" className="sr-only">{`Folie ${nr} von ${anzahl}: ${folie.titel}`}</p>

        {notizenAn && (
          <section
            aria-label="Sprechnotizen"
            className={`flex flex-col gap-1 border-t pt-3 ${vollbild ? `${BUEHNE.linie} text-paper` : "border-line text-slate"}`}
          >
            <h2 className={`font-sans text-14 font-bold ${vollbild ? "text-paper" : "text-ink"}`}>{`Sprechtext${zeitZeile}`}</h2>
            {folie.notizen ?? <p className="font-sans text-14">Zu dieser Folie gibt es keinen Sprechtext.</p>}
          </section>
        )}

        <div className={`${vollbild ? "hidden" : "flex"} flex-wrap items-center gap-[10px]`}>
          <Knopf art="sekundaer" onClick={() => gehe(nr - 1)} disabled={nr <= 1}>
            Vorherige Folie
          </Knopf>
          <Knopf art="primaer" onClick={() => gehe(nr + 1)} disabled={nr >= anzahl}>
            Nächste Folie
          </Knopf>
          <span className="px-2 font-sans text-14 tabular-nums text-slate">{`${nr} von ${anzahl}`}</span>
          <span className="flex-1" />
          <Knopf art="sekundaer" onClick={schalteVollbild} aria-pressed={vollbild} disabled={!kannVollbild}>
            Vollbild
          </Knopf>
          <Knopf art="sekundaer" onClick={() => setNotizenAn((an) => !an)} aria-pressed={notizenAn}>
            Notizen
          </Knopf>
        </div>
      </div>
    </div>
  );
}
