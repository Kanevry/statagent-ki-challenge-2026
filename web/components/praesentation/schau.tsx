"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Knopf } from "@kic/ui/basis";
import type { Folie } from "../../lib/praesentation/folien";
import { naechsterStand, schalterFuerTaste, type Stand } from "../../lib/praesentation/navigation";
import { BUEHNE, BUEHNE_BREITE, BUEHNE_HOEHE } from "./buehne-klassen";
import { istRuhig, k } from "./szenen/gemeinsam";
import { szeneFuer } from "./szenen";

/** Eine Folie, wie die Schau sie braucht: Beschriftung für die Leiste und fertig gebaute Teile vom Server. */
export interface SchauFolie {
  id: string;
  titel: string;
  /** Anfang der Zeitangabe, z. B. `3:15` */
  zeit?: string;
  /** Zeitangabe zum Lesen, z. B. `3:15 bis 4:15` */
  zeitText?: string;
  /** Generisches Layout vom Server; gilt, wenn `szene` fehlt oder unbekannt ist. */
  inhalt: ReactNode;
  /** `null`, wenn die Folie keinen Sprechtext hat */
  notizen: ReactNode | null;
  /** Animierte Szene aus der Registry (web/components/praesentation/szenen), mit den Daten der Folie. */
  szene?: { id: string; folie: Folie };
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
  const takte = useMemo(() => folien.map((f) => szeneFuer(f.szene?.id)?.takte ?? 0), [folien]);
  const [stand, setStand] = useState<Stand>({ folie: start, takt: 0 });
  const [notizenAn, setNotizenAn] = useState(false);
  const [vollbild, setVollbild] = useState(false);
  const [kannVollbild, setKannVollbild] = useState(true);
  const [skala, setSkala] = useState(0.5);
  const wurzel = useRef<HTMLDivElement>(null);
  const platz = useRef<HTMLDivElement>(null);
  const nr = stand.folie;
  const takt = stand.takt;
  const maxTakt = takte[nr - 1] ?? 0;
  const folie = folien[nr - 1] ?? folien[0];

  const wechsle = useCallback((neu: Stand) => {
    setStand(neu);
    const adresse = new URL(window.location.href);
    if (adresse.searchParams.get("folie") !== String(neu.folie)) {
      adresse.searchParams.set("folie", String(neu.folie));
      window.history.replaceState(null, "", adresse);
    }
  }, []);

  /** Sprung auf eine Folie (Leiste): Takt 0, bei reduzierter Bewegung alle Takte. */
  const gehe = useCallback(
    (ziel: number) => wechsle({ folie: ziel, takt: istRuhig() ? (takte[ziel - 1] ?? 0) : 0 }),
    [takte, wechsle],
  );

  const schritt = useCallback(
    (taste: string) => {
      const neu = naechsterStand(stand, takte, taste, istRuhig());
      if (neu && (neu.folie !== stand.folie || neu.takt !== stand.takt)) wechsle(neu);
      return neu !== null;
    },
    [stand, takte, wechsle],
  );

  // Reduzierte Bewegung: schon die Startfolie zeigt alle Takte (Endzustand wie im Prototyp).
  useEffect(() => {
    if (istRuhig()) setStand((s) => ({ ...s, takt: takte[s.folie - 1] ?? 0 }));
  }, [takte]);

  // Szenenwechsel wie im Prototyp: die alte Szene blendet 300 ms aus (.geht), Kreise mit gleicher Nummer
  // (data-k) gleiten per FLIP von ihrer alten an ihre neue Stelle. Bei reduzierter Bewegung: harter Wechsel.
  const buehne = useRef<HTMLDivElement>(null);
  const vorher = useRef(nr);
  useLayoutEffect(() => {
    const alt = vorher.current;
    vorher.current = nr;
    const el = buehne.current;
    if (!el || alt === nr) return;
    const [geht, geflogen, mitgenommen] = [k("geht"), k("geflogen"), k("mitgenommen")];
    el.querySelectorAll(`.${geht}`).forEach((s) => s.classList.remove(geht));
    el.querySelectorAll("[data-k]").forEach((kr) => kr.classList.remove(geflogen, mitgenommen));
    const altEl = el.querySelector<HTMLElement>(`[data-nr="${alt}"]`);
    const neuEl = el.querySelector<HTMLElement>(`[data-nr="${nr}"]`);
    if (!altEl || !neuEl || istRuhig()) return;
    altEl.classList.add(geht);
    const uhr = window.setTimeout(() => altEl.classList.remove(geht), 320);
    const massstab = el.getBoundingClientRect().width / BUEHNE_BREITE || 1;
    for (const neu of neuEl.querySelectorAll<HTMLElement>("[data-k]")) {
      const altKreis = altEl.querySelector<HTMLElement>(`[data-k="${neu.dataset.k ?? ""}"]`);
      if (!altKreis) continue;
      const a = altKreis.getBoundingClientRect();
      const b = neu.getBoundingClientRect();
      if (b.width === 0) continue;
      const dx = (a.left - b.left) / massstab;
      const dy = (a.top - b.top) / massstab;
      const sc = a.width / b.width;
      neu.classList.add(geflogen);
      altKreis.classList.add(mitgenommen);
      if (typeof neu.animate === "function" && (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5 || Math.abs(sc - 1) > 0.005)) {
        neu.animate([{ transform: `translate(${dx}px, ${dy}px) scale(${sc})` }, { transform: "none" }], {
          duration: 800,
          easing: "cubic-bezier(.2,.7,.2,1)",
        });
      }
    }
    return () => window.clearTimeout(uhr);
  }, [nr]);

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
      if (schritt(e.key)) {
        e.preventDefault();
        return;
      }
      const schalter = schalterFuerTaste(e.key);
      if (schalter === "notizen") setNotizenAn((an) => !an);
      else if (schalter === "vollbild") schalteVollbild();
    };
    window.addEventListener("keydown", beiTaste);
    return () => window.removeEventListener("keydown", beiTaste);
  }, [schritt, schalteVollbild]);

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
      className={`${k("praesentation")} flex min-h-0 flex-1 ${vollbild ? `h-dvh flex-col gap-4 p-4 ${BUEHNE.grund}` : ""}`}
    >
      <nav
        aria-label="Folien"
        className={`${k("ohne-druck")} ${vollbild ? "hidden" : "hidden lg:flex"} w-[300px] shrink-0 flex-col gap-1 overflow-y-auto border-r border-line bg-white p-4`}
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
        <p className="mt-auto pt-4 font-sans text-12 text-slate">Pfeiltasten: Folie und Takt. F: Vollbild. N: Notizen.</p>
      </nav>

      <div className={`flex min-w-0 flex-1 flex-col gap-4 ${vollbild ? "min-h-0" : "p-4 md:p-6"}`}>
        <div ref={platz} className={vollbild ? "flex min-h-0 flex-1 items-center justify-center" : "w-full"}>
          <section
            aria-roledescription="Folie"
            aria-label={`Folie ${nr} von ${anzahl}: ${folie.titel}`}
            data-folie={nr}
            data-folie-id={folie.id}
            data-takt={takt}
            style={{ width: BUEHNE_BREITE * skala, height: BUEHNE_HOEHE * skala }}
            className={`${k("rahmen")} relative shrink-0 overflow-hidden ${BUEHNE.grund}`}
          >
            <div
              style={{ width: BUEHNE_BREITE, height: BUEHNE_HOEHE, transform: `scale(${skala})`, transformOrigin: "top left" }}
              ref={buehne}
              className={`${k("buehne")} absolute left-0 top-0`}
            >
              {/* Alle Folien liegen im DOM, sichtbar ist nur die aktive (.aktiv). Beim Betreten starten ihre
                  Keyframes neu; im Druck stehen alle untereinander im Endzustand. */}
              {folien.map((f, i) => {
                const aktiv = i + 1 === nr;
                const eintrag = szeneFuer(f.szene?.id);
                return (
                  <div
                    key={f.id}
                    className={k("szene", aktiv && "aktiv")}
                    data-nr={i + 1}
                    data-szene={eintrag ? f.szene?.id : undefined}
                    data-aktiv={aktiv ? "ja" : undefined}
                  >
                    {eintrag && f.szene ? (
                      <eintrag.Komponente
                        folie={f.szene.folie}
                        nr={i + 1}
                        aktiv={aktiv}
                        takt={aktiv ? takt : (takte[i] ?? 0)}
                      />
                    ) : (
                      f.inhalt
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        </div>

        <p role="status" className="sr-only">{`Folie ${nr} von ${anzahl}: ${folie.titel}${maxTakt > 0 ? `, Takt ${takt} von ${maxTakt}` : ""}`}</p>

        {notizenAn && (
          <section
            aria-label="Sprechnotizen"
            className={`${k("ohne-druck")} flex flex-col gap-1 border-t pt-3 ${vollbild ? `${BUEHNE.linie} text-paper` : "border-line text-slate"}`}
          >
            <h2 className={`font-sans text-14 font-bold ${vollbild ? "text-paper" : "text-ink"}`}>{`Sprechtext${zeitZeile}`}</h2>
            {folie.notizen ?? <p className="font-sans text-14">Zu dieser Folie gibt es keinen Sprechtext.</p>}
          </section>
        )}

        <div className={`${k("ohne-druck")} ${vollbild ? "hidden" : "flex"} flex-wrap items-center gap-[10px]`}>
          <Knopf art="sekundaer" onClick={() => schritt("ArrowLeft")} disabled={nr <= 1 && takt <= 0}>
            Vorherige Folie
          </Knopf>
          <Knopf art="primaer" onClick={() => schritt("ArrowRight")} disabled={nr >= anzahl && takt >= maxTakt}>
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
