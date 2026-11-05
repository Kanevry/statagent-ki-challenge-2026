"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { memo, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { BUNDESLAENDER_2024_08, GOLDEN_SET, zahl } from "../daten/fakten";
import { berechneLayout, standardRaender, type SzeneLayout } from "../szene/motor/layout";
import { MARKEN, RUHE_P, schrittAnteil } from "../szene/motor/zeitplan";
import {
  SCHRITTE,
  STRECKE_VH,
  erzeugeFortschritt,
  type FortschrittSpeicher,
  type SchrittId,
  type SzeneVariante,
} from "../szene/vertrag";
import { BELEG, HERO, NAVIGATION, SCHRITT_TEXTE, SZENE_TEXTE, monateLesbar } from "../texte/inhalt";
import h from "./hero.module.css";
import s from "./seite.module.css";

const SzeneCanvas = dynamic(() => import("../szene/SzeneCanvas"), { ssr: false });

/** Bis hierhin steht der Erststand (Titel), danach übernimmt Schritt 1. */
const ERSTSTAND_BIS = 0.07;

/** Rastpunkte der Scroll-Strecke: Erststand und die Ruhepunkte der vier Schritte (alle Übergänge fertig). */
const RASTPUNKTE = [0, ...SCHRITTE.map((schritt) => RUHE_P[schritt.id])];

/** Fester Fortschritt des Standbilds bei reduzierter Bewegung. */
const STANDBILD_P = 0.62;
const ZAEHLEN_MS = 600;

/** Sichtbarer Bereich je Schritt (Schritt 1 beginnt nach dem Erststand). */
const BEREICHE = SCHRITTE.map((schritt, i) => ({
  ...schritt,
  von: i === 0 ? ERSTSTAND_BIS : schritt.von,
}));

/** Welche DOM-Beschriftungen zur Szene passen: nur wenn die Partikel ruhen (MARKEN in zeitplan.ts). */
function markenPhase(p: number): "" | "befunde" | "karte" | "tabelle" {
  const s2 = schrittAnteil(p, "pruefen");
  const s3 = schrittAnteil(p, "zaehlen");
  const s4 = schrittAnteil(p, "belegen");
  if (p >= SCHRITTE[3].von) return s4 >= MARKEN.tabelleAb ? "tabelle" : s4 < MARKEN.karteBisS4 ? "karte" : "";
  if (p >= SCHRITTE[2].von) return s3 >= MARKEN.karteAb ? "karte" : s3 < MARKEN.befundeBisS3 ? "befunde" : "";
  if (p >= SCHRITTE[1].von) return s2 >= MARKEN.befundeAb ? "befunde" : "";
  return "";
}

function aktiverSchritt(p: number): number {
  if (p < ERSTSTAND_BIS) return -1;
  const i = BEREICHE.findIndex((b) => p >= b.von && p < b.bis);
  return i === -1 ? BEREICHE.length - 1 : i;
}

/**
 * Schritt 4: Die Szene zeichnet je Bundesland einen Punkt-Balken und lässt links Platz für den
 * Namen, rechts für die Zahl. Die DOM-Tabelle setzt beides an die Koordinaten aus berechneLayout,
 * mit denselben Rändern wie der Motor (standardRaender, vollflächiges Canvas = Bühne).
 * Vor der Messung und ohne Sticky-Strecke steht die Tabelle als normale Tabelle da.
 */
interface TabellenAnker {
  /** gleiche Geometrie wie die Szene (Event `szenelayout` des Motors, sonst selbst berechnet) */
  layout: SzeneLayout;
  /** mobil: Kürzel statt Namen (die Szene lässt dort nur 40 px) */
  kurz: boolean;
  breite: number;
  hoehe: number;
  zeilen: { code: number; y: number; x0: number; x1: number }[];
}

const LUECKE_PX = 10;

interface Modus {
  bereit: boolean;
  variante: SzeneVariante;
  reduziert: boolean;
}

export default function HeroSzene() {
  const abschnittRef = useRef<HTMLElement>(null);
  const buehneRef = useRef<HTMLDivElement>(null);
  const fuellungen = useRef<(HTMLSpanElement | null)[]>([]);
  const speicher = useRef<FortschrittSpeicher | null>(null);
  if (speicher.current === null) speicher.current = erzeugeFortschritt();
  const fortschritt = speicher.current;

  const [modus, setModus] = useState<Modus>({ bereit: false, variante: "desktop", reduziert: false });
  const [aktiv, setAktiv] = useState(-1);
  const [anker, setAnker] = useState<TabellenAnker | null>(null);

  // Variante und reduzierte Bewegung aus den Media Queries, auch bei Änderung zur Laufzeit.
  useEffect(() => {
    const schmal = window.matchMedia("(max-width: 767px)");
    const ruhig = window.matchMedia("(prefers-reduced-motion: reduce)");
    const lesen = () =>
      setModus({ bereit: true, variante: schmal.matches ? "mobil" : "desktop", reduziert: ruhig.matches });
    lesen();
    schmal.addEventListener("change", lesen);
    ruhig.addEventListener("change", lesen);
    return () => {
      schmal.removeEventListener("change", lesen);
      ruhig.removeEventListener("change", lesen);
    };
  }, []);

  // Fortschritt → aktiver Schritt (React-State nur beim Wechsel) und Füllstand der Leiste (direkt im DOM).
  useEffect(() => {
    let phase = "-";
    const anwenden = (p: number) => {
      setAktiv(aktiverSchritt(p));
      const neu = markenPhase(p);
      if (neu !== phase && abschnittRef.current) {
        phase = neu;
        abschnittRef.current.dataset.marken = neu;
      }
      BEREICHE.forEach((b, i) => {
        const el = fuellungen.current[i];
        if (!el) return;
        const anteil = Math.min(1, Math.max(0, (p - b.von) / (b.bis - b.von)));
        el.style.transform = `scaleX(${anteil})`;
      });
    };
    anwenden(fortschritt.wert());
    return fortschritt.abonnieren(anwenden);
  }, [fortschritt]);

  // Scroll-Scrubbing nur ohne reduzierte Bewegung; sonst steht das Standbild fest.
  useEffect(() => {
    if (!modus.bereit) return;
    if (modus.reduziert) {
      fortschritt.setzen(STANDBILD_P);
      return;
    }
    let rahmen = 0;
    const messen = () => {
      rahmen = 0;
      const el = abschnittRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const strecke = r.height - window.innerHeight;
      fortschritt.setzen(strecke > 0 ? -r.top / strecke : 0);
    };
    const anfordern = () => {
      if (!rahmen) rahmen = requestAnimationFrame(messen);
    };
    messen();
    window.addEventListener("scroll", anfordern, { passive: true });
    window.addEventListener("resize", anfordern, { passive: true });
    // Weiches Einrasten: Bleibt das Scrollen in der Nähe eines Ruhepunkts stehen, gleitet die Seite
    // dorthin (Anker unten in der Strecke). „proximity“ statt „mandatory“: Weit weg davon und beim
    // schnellen Wischen bleibt das Scrollen frei, der Rest der Seite rastet nie ein.
    const wurzel = document.documentElement;
    const vorher = wurzel.style.scrollSnapType;
    wurzel.style.scrollSnapType = "y proximity";
    return () => {
      window.removeEventListener("scroll", anfordern);
      window.removeEventListener("resize", anfordern);
      if (rahmen) cancelAnimationFrame(rahmen);
      wurzel.style.scrollSnapType = vorher;
    };
  }, [modus.bereit, modus.reduziert, fortschritt]);

  // Tabelle und Szene teilen dieselbe Geometrie (Bühne = vollflächiges Canvas). Ohne Sticky-Strecke
  // steht die Tabelle im Textfluss.
  useEffect(() => {
    const buehne = buehneRef.current;
    if (!modus.bereit || modus.reduziert || !buehne) {
      setAnker(null);
      return;
    }
    const uebernehmen = (l: SzeneLayout) => {
      const u = l.tabelle.unbekannt;
      setAnker({
        layout: l,
        kurz: l.variante === "mobil",
        breite: l.breite,
        hoehe: l.hoehe,
        zeilen: [
          ...l.tabelle.zeilen.map((z) => ({ code: z.code, y: z.y, x0: z.x0, x1: z.x1 })),
          { code: 0, y: u.y + u.hoehe / 2, x0: u.x, x1: u.x + u.breite },
        ],
      });
    };
    // Vor dem ersten Bild des Motors (mobil: bis zur ersten Interaktion) dieselbe Rechnung ohne
    // Kartenmeta. Marken und Tabelle sind erst ab Schritt 2 sichtbar: im Leerlauf rechnen, nicht in
    // der Aufgabe der Hydration, und nur bei geänderter Größe neu.
    let vomMotor = false;
    let gemessen = "";
    const messen = () => {
      if (vomMotor) return;
      const { width: b, height: hh } = buehne.getBoundingClientRect();
      const schluessel = `${b}x${hh}`;
      if (schluessel === gemessen) return;
      gemessen = schluessel;
      if (b < 200 || hh < 200) return setAnker(null);
      const v = modus.variante;
      uebernehmen(berechneLayout(b, hh, v, null, standardRaender(b, hh, v, true)));
    };
    const mitIdle = typeof window.requestIdleCallback === "function";
    let auftrag = 0;
    const planen = () => {
      if (auftrag) return;
      auftrag = mitIdle
        ? window.requestIdleCallback(() => ((auftrag = 0), messen()), { timeout: 600 })
        : window.setTimeout(() => ((auftrag = 0), messen()), 200);
    };
    const vomEvent = (e: Event) => {
      const l = (e as CustomEvent<SzeneLayout>).detail;
      if (!l || l.variante !== modus.variante) return;
      vomMotor = true;
      uebernehmen(l);
    };
    buehne.addEventListener("szenelayout", vomEvent);
    // Der erste Aufruf des Beobachters kommt sofort nach observe und plant die erste Messung.
    const beobachter = new ResizeObserver(planen);
    beobachter.observe(buehne);
    return () => {
      beobachter.disconnect();
      buehne.removeEventListener("szenelayout", vomEvent);
      if (auftrag) {
        if (mitIdle) window.cancelIdleCallback(auftrag);
        else window.clearTimeout(auftrag);
      }
    };
  }, [modus]);

  const springe = (i: number) => {
    const el = abschnittRef.current;
    if (!el) return;
    // Auf den Ruhepunkt des Schritts: nach dem Klick steht ein fertiges Bild
    const ziel = RUHE_P[BEREICHE[i].id];
    const oben = el.getBoundingClientRect().top + window.scrollY;
    const strecke = el.offsetHeight - window.innerHeight;
    window.scrollTo({ top: oben + ziel * strecke, behavior: modus.reduziert ? "auto" : "smooth" });
  };

  // Das Canvas bekommt nur neue Props, wenn sich der Modus ändert, nicht bei jedem Schrittwechsel.
  const canvas = useMemo(
    () =>
      modus.bereit ? (
        <SzeneCanvas
          className={h.canvas}
          fortschritt={fortschritt}
          variante={modus.variante}
          reduziert={modus.reduziert}
        />
      ) : null,
    [modus.bereit, modus.variante, modus.reduziert, fortschritt],
  );

  const zaehlen = modus.bereit && !modus.reduziert;
  const strecke = {
    "--strecke-desktop": STRECKE_VH.desktop,
    "--strecke-mobil": STRECKE_VH.mobil,
  } as CSSProperties;

  const lage = (i: number) => (i === aktiv ? "aktiv" : i < aktiv ? "vorher" : "nachher");

  return (
    <section
      ref={abschnittRef}
      id="start"
      className={h.hero}
      style={strecke}
      data-szene=""
      aria-labelledby="hero-titel"
    >
      {zaehlen ? (
        <div className={h.anker} aria-hidden="true">
          {RASTPUNKTE.map((p) => (
            <span key={p} style={{ "--p": p } as CSSProperties} />
          ))}
        </div>
      ) : null}
      <div ref={buehneRef} className={h.buehne}>
        {canvas}
        {anker ? <SzenenMarken layout={anker.layout} /> : null}
        <div className={h.ebene}>
          <div className={h.texte}>
            <div className={h.erststand} data-lage={lage(-1)}>
              <ErststandInhalt />
            </div>

            {SCHRITTE.map((schritt, i) => {
              const t = SCHRITT_TEXTE[schritt.id];
              return (
                <article
                  key={schritt.id}
                  className={h.schritt}
                  data-schritt={schritt.id}
                  data-lage={lage(i)}
                  aria-labelledby={`schritt-${schritt.id}`}
                >
                  <div className={h.schrittText}>
                    <SchrittTitel id={schritt.id} />
                    <p className={h.kennzahlZeile}>
                      <Kennzahl
                        wert={t.kennzahl}
                        aktiv={aktiv === i}
                        zaehlen={zaehlen}
                        className={schritt.id === "belegen" ? h.kennzahlBelegt : h.kennzahl}
                      />
                      <span className={h.einheit}>{t.einheit}</span>
                    </p>
                    <SchrittErklaerung id={schritt.id} />
                  </div>
                  {schritt.id === "belegen" ? <LaenderTabelle anker={anker} /> : null}
                </article>
              );
            })}
          </div>

          <ol className={h.leiste} aria-label={HERO.schritteBereich}>
            {BEREICHE.map((b, i) => (
              <li key={b.id} className={h.leisteTeil}>
                <button
                  type="button"
                  className={h.leisteKnopf}
                  aria-current={aktiv === i ? "step" : undefined}
                  onClick={() => springe(i)}
                >
                  <span className={h.leisteNr}>{i + 1}</span>
                  <span className={h.leisteName}>
                    <span className={s.nurLeser}>{HERO.springeZu} </span>
                    {SCHRITT_TEXTE[b.id].marke}
                  </span>
                  <span className={h.spur} aria-hidden="true">
                    <span
                      className={h.fuellung}
                      ref={(el) => {
                        fuellungen.current[i] = el;
                      }}
                    />
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

/**
 * Statische Textblöcke als memo-Komponenten: Sie ändern sich nie, Re-Renders der Szene (Modus,
 * aktiver Schritt, Anker) überspringen sie.
 */
const ErststandInhalt = memo(function ErststandInhalt() {
  return (
    <>
      <h1 id="hero-titel" className={h.titel}>
        {HERO.titel} <span className={h.autor}>{HERO.autor}</span>
      </h1>
      <p className={h.satz}>{HERO.satz}</p>
      <Link href={NAVIGATION.app.href} className={h.appKnopf}>
        {NAVIGATION.app.text}
      </Link>
      <div className={h.ergebnis}>
        <dl className={h.ergebnisListe} aria-label={HERO.ergebnisBereich}>
          {HERO.ergebnis.map((e) => (
            <div key={e.text} className={h.ergebnisPunkt}>
              <dt className={h.ergebnisText}>{e.text}</dt>
              <dd className={h.ergebnisWert}>{e.wert}</dd>
            </div>
          ))}
        </dl>
        <p className={h.ergebnisQuelle}>{HERO.ergebnisQuelle}</p>
      </div>
      <p className={h.hinweis}>{HERO.hinweis}</p>
    </>
  );
});

const SchrittTitel = memo(function SchrittTitel({ id }: { id: SchrittId }) {
  return (
    <h2 id={`schritt-${id}`} className={h.schrittTitel}>
      {SCHRITT_TEXTE[id].titel}
    </h2>
  );
});

const SchrittErklaerung = memo(function SchrittErklaerung({ id }: { id: SchrittId }) {
  const t = SCHRITT_TEXTE[id];
  return (
    <>
      <p className={h.schrittSatz}>{t.text}</p>
      {t.glossar.map((g) => (
        <p key={g.begriff} className={h.glossar}>
          <dfn>{g.begriff}</dfn>: {g.erklaerung}
        </p>
      ))}
      {id === "belegen" ? (
        <figure className={h.beleg}>
          <pre className={h.code}>
            <code>{BELEG.sql}</code>
          </pre>
          <figcaption className={h.belegText}>{BELEG.unterschrift}</figcaption>
        </figure>
      ) : null}
    </>
  );
});

/** Große Kennzahl; zählt beim Aktivwerden in höchstens 600 ms hoch. SSR und ohne JS: Endwert. */
function Kennzahl({
  wert,
  aktiv,
  zaehlen,
  className,
}: {
  wert: number;
  aktiv: boolean;
  zaehlen: boolean;
  className: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const knoten = ref.current?.firstChild;
    if (!(knoten instanceof Text)) return;
    const ende = zahl(wert);
    if (!aktiv || !zaehlen) {
      knoten.data = ende;
      return;
    }
    let start = 0;
    let rahmen = requestAnimationFrame(function schritt(t) {
      if (!start) start = t;
      const k = Math.min(1, (t - start) / ZAEHLEN_MS);
      const weich = 1 - Math.pow(1 - k, 3);
      knoten.data = k < 1 ? zahl(wert * weich) : ende;
      if (k < 1) rahmen = requestAnimationFrame(schritt);
    });
    return () => {
      cancelAnimationFrame(rahmen);
      knoten.data = ende;
    };
  }, [aktiv, zaehlen, wert]);

  return (
    <span ref={ref} className={className}>
      {zahl(wert)}
    </span>
  );
}

/**
 * Beschriftungen an der Szene (Schritt 2: Befund-Gruppen; Schritt 3: Länder, Gruppe ohne Bundesland,
 * Auflösung der Karte). Sichtbarkeit steuert `data-marken` am Abschnitt, damit Text und Partikel
 * gemeinsam ruhen. Die Zahlen stehen zugänglich in Schritt-Texten, Tabelle und Abschnitt Datenfehler.
 */
const SzenenMarken = memo(function SzenenMarken({ layout: l }: { layout: SzeneLayout }) {
  const mobil = l.variante === "mobil";
  const k = l.karte;
  const linien = l.bundeslaender
    .filter((b) => b.fuehrung)
    .map((b) => {
      const senkrecht = Math.abs(b.ly - b.y) > Math.abs(b.lx - b.x);
      if (senkrecht) {
        const richtung = Math.sign(b.ly - b.y) || 1;
        return { code: b.code, x1: b.x, y1: b.y + 3 * richtung, x2: b.x, y2: b.ly - 9 * richtung };
      }
      const richtung = Math.sign(b.lx - b.x) || 1;
      return { code: b.code, x1: b.x + 3 * richtung, y1: b.y, x2: b.lx - 5 * richtung, y2: b.y };
    });
  return (
    <div className={h.marken} aria-hidden="true">
      <div className={h.markenBefunde}>
        {l.befunde.map((b) => (
          <p
            key={b.id}
            className={h.befundMarke}
            style={{ left: b.label.x, top: b.label.y, width: b.label.breite }}
          >
            <span className={h.markeZahl}>{zahl(b.zeilen)}</span> {(mobil && SZENE_TEXTE.befundMobil[b.id]) || SZENE_TEXTE.befund[b.id]}{" "}
            <span className={h.befundLieferung}>{monateLesbar(b.lieferung)}</span>
          </p>
        ))}
      </div>
      <div className={h.markenKarte}>
        <svg className={h.fuehrung} width={l.breite} height={l.hoehe}>
          {linien.map((x) => (
            <line key={x.code} x1={x.x1} y1={x.y1} x2={x.x2} y2={x.y2} />
          ))}
        </svg>
        {l.bundeslaender.map((b) => (
          <p
            key={b.code}
            className={h.landMarke}
            data-ausrichtung={b.ausrichtung}
            style={{ left: b.lx, top: b.ly }}
          >
            {mobil ? b.kurz : b.name} <span className={h.markeZahl}>{zahl(b.anzahl)}</span>
          </p>
        ))}
        <p
          className={h.befundMarke}
          style={{ left: k.unbekanntLabel.x, top: k.unbekanntLabel.y, width: k.unbekanntLabel.breite }}
        >
          <span className={h.markeZahl}>{zahl(BUNDESLAENDER_2024_08.find((b) => b.code === 0)?.anzahl ?? 0)}</span>{" "}
          {SZENE_TEXTE.unbekannt}
        </p>
        <p className={h.legende} style={{ left: k.legende.x, top: k.legende.y, width: k.legende.breite }}>
          {SZENE_TEXTE.legende(k.verhaeltnisseProPunkt)}
        </p>
      </div>
    </div>
  );
});

const LaenderTabelle = memo(function LaenderTabelle({ anker }: { anker: TabellenAnker | null }) {
  const nachCode = new Map(BUNDESLAENDER_2024_08.map((b) => [b.code as number, b]));
  const absteigend = [...BUNDESLAENDER_2024_08]
    .filter((b) => b.code !== 0)
    .sort((a, b) => b.anzahl - a.anzahl)
    .map((b) => ({ code: b.code as number, y: 0, x0: 0, x1: 0 }));
  const zeilen = anker?.zeilen ?? [...absteigend, { code: 0, y: 0, x0: 0, x1: 0 }];

  const koerper = (
    <tbody>
      {zeilen.map((z) => {
        const b = nachCode.get(z.code);
        if (!b) return null;
        return (
          <tr key={b.code} data-unbekannt={b.code === 0 ? "" : undefined} style={anker ? { top: z.y } : undefined}>
            <th scope="row" style={anker ? { right: anker.breite - z.x0 + LUECKE_PX } : undefined}>
              {anker?.kurz ? (
                <>
                  <span aria-hidden="true">{b.kurz}</span>
                  <span className={s.nurLeser}>{b.name}</span>
                </>
              ) : (
                b.name
              )}
            </th>
            <td style={anker ? { left: z.x1 + LUECKE_PX } : undefined}>{zahl(b.anzahl)}</td>
          </tr>
        );
      })}
    </tbody>
  );
  const kopf = (
    <>
      <caption className={s.nurLeser}>{BELEG.tabelle}</caption>
      <thead className={s.nurLeser}>
        <tr>
          <th scope="col">{BELEG.spalteLand}</th>
          <th scope="col">{BELEG.spalteAnzahl}</th>
        </tr>
      </thead>
    </>
  );

  if (anker) {
    return (
      // Ebene ist höchstens 1440 px breit und zentriert, die Koordinaten gelten für die ganze Bühne.
      <table
        className={h.laenderAnker}
        style={{ left: `calc(50% - ${anker.breite / 2}px)`, width: anker.breite, height: anker.hoehe }}
      >
        {kopf}
        {koerper}
      </table>
    );
  }

  return (
    <div className={h.laenderRahmen}>
      <p className={h.laenderTitel} aria-hidden="true">
        {BELEG.tabelle}
      </p>
      <table className={h.laender}>
        {kopf}
        {koerper}
        <tfoot className={h.laenderSumme}>
          <tr>
            <th scope="row">{BELEG.summe}</th>
            <td>{zahl(GOLDEN_SET.bestand)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
});
