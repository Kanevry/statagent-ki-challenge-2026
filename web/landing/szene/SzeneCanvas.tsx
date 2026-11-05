"use client";

import { useEffect, useRef, useState } from "react";
import { LIEFERUNGEN } from "../daten/fakten";
import { berechneLayout, planePartikel, PUNKT_STIL, raster, standardRaender, type SzeneLayout } from "./motor/layout";
import type { SzeneCanvasProps, SzeneVariante } from "./vertrag";

/**
 * Bühne der Landing-Szene. Desktop: three.js lädt nach dem ersten Bild (requestIdleCallback, sonst
 * 200 ms). Mobil: erst bei der ersten Interaktion (scroll, touchstart, pointerdown, keydown); bis
 * dahin steht ein statisches Bild der 24 Säulen in derselben Lage und Farbwelt wie Schritt 1, der
 * Motor übernimmt ohne Ladeanimation. Ohne WebGL2 bleibt ein statisches SVG der 24 Lieferungen.
 * Größe und Lage steuert die Seite über `className` (Breite und Höhe müssen dort festgelegt sein).
 */
export default function SzeneCanvas({ fortschritt, variante, reduziert, className }: SzeneCanvasProps) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [ohneWebgl, setOhneWebgl] = useState(false);
  const aufInteraktion = variante === "mobil" && !reduziert;
  const [statisch, setStatisch] = useState(aufInteraktion);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    let abgebrochen = false;
    let handle: { zerstoeren(): void } | null = null;

    const start = async () => {
      if (abgebrochen) return;
      if (!hatWebgl2()) {
        setOhneWebgl(true);
        return;
      }
      try {
        const [motor, karte] = await Promise.all([import("./motor/motor"), import("./motor/karte")]);
        if (abgebrochen) return;
        const punkte = planePartikel(variante).kartenPartikel;
        handle = motor.starteSzene({
          canvas,
          fortschritt,
          variante,
          reduziert,
          ohneLaden: aufInteraktion,
          beiErstemBild: () => {
            if (!abgebrochen) setStatisch(false);
          },
          ladeKarte: () => karte.ladeKartePraefix(punkte),
        });
        if (!handle) setOhneWebgl(true);
      } catch {
        if (!abgebrochen) setOhneWebgl(true);
      }
    };

    if (aufInteraktion) {
      const ereignisse = ["scroll", "touchstart", "pointerdown", "keydown"] as const;
      let gestartet = false;
      const los = () => {
        if (gestartet) return;
        gestartet = true;
        for (const e of ereignisse) window.removeEventListener(e, los);
        void start();
      };
      for (const e of ereignisse) window.addEventListener(e, los, { once: true, passive: true });
      return () => {
        abgebrochen = true;
        for (const e of ereignisse) window.removeEventListener(e, los);
        handle?.zerstoeren();
      };
    }

    // Safari kennt requestIdleCallback erst spät; dann 200 ms nach dem ersten Bild.
    const mitIdle = typeof window.requestIdleCallback === "function";
    const id = mitIdle
      ? window.requestIdleCallback(() => void start(), { timeout: 800 })
      : window.setTimeout(() => void start(), 200);
    return () => {
      abgebrochen = true;
      if (mitIdle) window.cancelIdleCallback(id);
      else window.clearTimeout(id);
      handle?.zerstoeren();
    };
  }, [fortschritt, variante, reduziert, aufInteraktion]);

  if (ohneWebgl) return <SaeulenSvg className={className} />;
  return (
    <>
      <canvas
        key={`${variante}-${reduziert ? "r" : "b"}`}
        ref={ref}
        className={className}
        aria-hidden="true"
        style={{ display: "block", pointerEvents: "none" }}
      />
      {statisch ? <SaeulenStandbild className={className} variante={variante} /> : null}
    </>
  );
}

function hatWebgl2(): boolean {
  try {
    const c = document.createElement("canvas");
    const gl = c.getContext("webgl2");
    if (!gl) return false;
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return true;
  } catch {
    return false;
  }
}

/**
 * Schritt 1 als statisches SVG, deckungsgleich mit dem Motor: gleiche Layout-Funktion, je Säule das
 * Punktraster des Motors als Muster (ohne die 0,35-Zellen-Streuung), gleiche Punktgröße und Deckkraft.
 */
function SaeulenStandbild({ className, variante }: { className?: string; variante: SzeneVariante }) {
  const ref = useRef<SVGSVGElement>(null);
  const [layout, setLayout] = useState<SzeneLayout | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const messen = () => {
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return;
      const voll = r.width >= window.innerWidth * 0.9 && r.height >= window.innerHeight * 0.85;
      setLayout(berechneLayout(r.width, r.height, variante, null, standardRaender(r.width, r.height, variante, voll)));
    };
    messen();
    const ro = new ResizeObserver(messen);
    ro.observe(el);
    return () => ro.disconnect();
  }, [variante]);

  const stil = PUNKT_STIL[variante];
  // Kleiner als im Motor: die Streuung dort lässt Lücken, ein starres Raster gleicher Größe wirkt
  // sonst wie Streifen. Zwei versetzte Punkte je Kachel ahmen die Streuung nach.
  const radius = stil.groesse * 0.4;
  return (
    <svg
      ref={ref}
      className={className}
      aria-hidden="true"
      focusable="false"
      style={{ display: "block", pointerEvents: "none" }}
    >
      {layout ? (
        <>
          <defs>
            {layout.saeulen.map((s) => {
              const { nx, ny } = raster(s.partikel, s.rechts - s.links, s.unten - s.oben);
              const zw = (s.rechts - s.links) / nx;
              const zh = (s.unten - s.oben) / ny;
              return (
                <pattern
                  key={s.lieferung}
                  id={`saeule-${s.index}`}
                  patternUnits="userSpaceOnUse"
                  x={s.links}
                  y={s.oben}
                  width={zw}
                  height={zh * 2}
                >
                  <circle cx={zw * 0.38} cy={zh * 0.5} r={radius} fill="#F4F7F5" fillOpacity={stil.alpha} />
                  <circle cx={zw * 0.62} cy={zh * 1.5} r={radius} fill="#F4F7F5" fillOpacity={stil.alpha} />
                </pattern>
              );
            })}
          </defs>
          {layout.saeulen.map((s) => (
            <rect
              key={s.lieferung}
              x={s.links}
              y={s.oben}
              width={s.rechts - s.links}
              height={s.unten - s.oben}
              fill={`url(#saeule-${s.index})`}
            />
          ))}
          <path
            d={achse(layout)}
            stroke="#F4F7F5"
            strokeOpacity={0.4}
            strokeWidth={1}
            fill="none"
            shapeRendering="crispEdges"
          />
        </>
      ) : null}
    </svg>
  );
}

function achse(l: SzeneLayout): string {
  const y = Math.round(l.grundlinie.y) + 0.5;
  let d = `M${l.grundlinie.links} ${y}H${l.grundlinie.rechts}`;
  for (const s of l.saeulen) {
    const jahr = s.lieferung.endsWith("-01") || s.index === 0;
    const x = Math.round(s.x) + 0.5;
    d += `M${x} ${y}V${y + (jahr ? 9 : 4)}`;
  }
  return d;
}

/** Statische Ersatzdarstellung ohne WebGL2: 24 Säulen ab Null, gleiche Farbwelt. */
function SaeulenSvg({ className }: { className?: string }) {
  const b = 960;
  const h = 540;
  const rand = 32;
  const grund = h - 48;
  const max = Math.max(...LIEFERUNGEN.map((l) => l.zeilen));
  const slot = (b - 2 * rand) / LIEFERUNGEN.length;
  const sb = slot * 0.68;
  return (
    <svg
      className={className}
      aria-hidden="true"
      focusable="false"
      viewBox={`0 0 ${b} ${h}`}
      preserveAspectRatio="xMidYMid meet"
      style={{ display: "block", pointerEvents: "none" }}
    >
      {LIEFERUNGEN.map((l, i) => {
        const hz = (l.zeilen / max) * (grund - rand);
        return (
          <rect
            key={l.lieferung}
            x={rand + slot * i + (slot - sb) / 2}
            y={grund - hz}
            width={sb}
            height={hz}
            fill="#F4F7F5"
            fillOpacity={0.62}
          />
        );
      })}
      <line x1={rand - 6} x2={b - rand + 6} y1={grund + 0.5} y2={grund + 0.5} stroke="#F4F7F5" strokeOpacity={0.4} />
    </svg>
  );
}
