"use client";

import Image from "next/image";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { Folie } from "../../../lib/praesentation/folien";
import type { Inline } from "../../../lib/praesentation/markdown";
import { herkunft, screenshotKennung, zeitZeile } from "../../../lib/praesentation/szenen-daten";
import { bildFuer } from "../bilder";
import stile from "../szenen.module.css";

// Achtung: aus lib/praesentation/folien.ts nur Typen importieren. Die Datei lädt node:fs und darf nicht in den Browser.

/** Was jede Szene bekommt: die geparste Folie, ihre Nummer, ob sie gerade läuft, und den gezeigten Takt. */
export interface SzeneProps {
  folie: Folie;
  nr: number;
  aktiv: boolean;
  takt: number;
}

const S = stile as Record<string, string | undefined>;

/** Klassen aus dem CSS-Modul; `false` und unbekannte Namen fallen weg bzw. bleiben wie sie sind. */
export function k(...namen: (string | false | undefined)[]): string {
  return namen
    .filter((n): n is string => typeof n === "string" && n !== "")
    .map((n) => S[n] ?? n)
    .join(" ");
}

/** CSS-Variablen (`--t`, `--i`, `--x` …) als Style-Objekt. */
export function vars(werte: Record<string, string | number>): CSSProperties {
  return Object.fromEntries(Object.entries(werte).map(([n, v]) => [`--${n}`, String(v)])) as CSSProperties;
}

const FORMAT = new Intl.NumberFormat("de-DE");

/** Nutzer wünscht reduzierte Bewegung. Auf dem Server und ohne matchMedia: nein. */
export function istRuhig(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

/** Text mit `**fett**` und `` `code` `` aus dem Parser, als React-Elemente. */
export function Text({ inline }: { inline: readonly Inline[] }) {
  return (
    <>
      {inline.map((t, i) =>
        t.art === "fett" ? <strong key={i}>{t.text}</strong> : t.art === "code" ? <code key={i}>{t.text}</code> : <span key={i}>{t.text}</span>,
      )}
    </>
  );
}

/** Fußzeile: links die Herkunft aus dem Markdown (falls vorhanden), rechts Nummer und Zeit. */
export function Fuss({ folie, nr }: { folie: Folie; nr: number }) {
  const quelle = herkunft(folie);
  return (
    <>
      {quelle && <p className={k("herkunft")}>{quelle}</p>}
      <p className={k("zeit")}>{zeitZeile(folie, nr)}</p>
    </>
  );
}

/**
 * Kreis einer Aufgabe (1, 2, 3) oder der gefüllte Kreis 4. `data-k` verbindet gleiche Kreise über den
 * Szenenwechsel (FLIP in schau.tsx). Position und Größe in px auf der Bühne, `t` = Auftritt in Sekunden.
 */
export function Kreis({ n, x, y, d, t, klasse }: { n: number; x: number; y: number; d: number; t?: number; klasse?: string }) {
  return (
    <div className={k("kreis", `k${n}`, klasse)} data-k={n} style={vars({ x: `${x}px`, y: `${y}px`, d: `${d}px`, ...(t === undefined ? {} : { t }) })}>
      <div className={k("kreis-koerper")} aria-hidden="true">
        {n}
      </div>
    </div>
  );
}

/** Gezeichneter Mint-Haken (SVG mit pathLength 1). */
export function Haken({ klasse, viewBox, d, t, dauer }: { klasse: string; viewBox: string; d: string; t: number; dauer?: number }) {
  return (
    <svg className={k(klasse, "haken")} viewBox={viewBox} aria-hidden="true">
      <path className={k("strich", "zeichnet")} style={vars({ t, ...(dauer ? { dauer: `${dauer}s` } : {}) })} pathLength={1} d={d} />
    </svg>
  );
}

/**
 * Blick in die App: ruhiges Fenster mit einem echten Bildschirmfoto aus bilder.ts. Ohne Bild zur Kennung aus
 * `screenshot:` erscheint nichts, der Platz bleibt leer.
 */
export function Blick({ folie, breite, t, wartet = false, style }: { folie: Folie; breite: number; t: number; wartet?: boolean; style?: CSSProperties }) {
  const kennung = screenshotKennung(folie);
  const bild = bildFuer(kennung);
  if (!bild || !kennung) return null;
  return (
    <figure className={k("blick", wartet && "blick-wartet")} style={{ ...vars({ b: `${breite}px`, t }), ...style }}>
      <Image src={bild} alt={`Blick in die App: ${folie.titel}`} fill sizes={`${breite}px`} unoptimized />
    </figure>
  );
}

/** Ablauf über requestAnimationFrame: ruft `schritt(ms seit Start)`, bis es `false` liefert. */
function useAblauf(aktiv: boolean, schritt: (ms: number) => boolean, ende: () => void, abh: readonly unknown[]) {
  useEffect(() => {
    if (!aktiv || istRuhig()) {
      ende();
      return;
    }
    let t0: number | null = null;
    let id = 0;
    const tick = (t: number) => {
      t0 ??= t;
      if (schritt(t - t0)) id = requestAnimationFrame(tick);
    };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
    // `schritt` und `ende` sind je Render neu; neu gestartet wird nur, wenn sich aktiv oder `abh` ändert.
  }, [aktiv, ...abh]);
}

/** Zählt beim Betreten von 0 auf `ziel` (1,2 s nach `start` ms). Ohne JavaScript und bei reduzierter Bewegung: Endwert. */
export function Zaehler({ ziel, aktiv, start = 0, className }: { ziel: number; aktiv: boolean; start?: number; className?: string }) {
  const [wert, setWert] = useState(ziel);
  useAblauf(
    aktiv && Number.isFinite(ziel),
    (ms) => {
      const p = Math.max(0, Math.min(1, (ms - start) / 1200));
      setWert(Math.round(ziel * (1 - Math.pow(1 - p, 3))));
      return p < 1;
    },
    () => setWert(ziel),
    [ziel, start],
  );
  return <p className={className}>{Number.isFinite(wert) ? FORMAT.format(wert) : ""}</p>;
}

/**
 * Tippt `text` beim Betreten Zeichen für Zeichen (`ms` je Zeichen, ab `start` ms). Der ganze Text steht immer im
 * DOM; der noch nicht getippte Rest ist nur unsichtbar, damit die Zeile nicht springt.
 */
export function Getippt({ text, aktiv, start = 0, ms = 30 }: { text: string; aktiv: boolean; start?: number; ms?: number }) {
  const [n, setN] = useState(text.length);
  useAblauf(
    aktiv,
    (zeit) => {
      const zeichen = Math.max(0, Math.min(text.length, Math.floor((zeit - start) / ms)));
      setN(zeichen);
      return zeichen < text.length;
    },
    () => setN(text.length),
    [text, start, ms],
  );
  return (
    <>
      <span aria-hidden="true">{text.slice(0, n)}</span>
      <span className={k("rest")} aria-hidden="true">
        {text.slice(n)}
      </span>
    </>
  );
}

/**
 * Raster aus `anzahl` Quadraten (11 px, Abstand 2 px) als Canvas. Beim Betreten füllt eine Welle von links oben
 * nach rechts unten die Zellen Mint (ab 0,3 s, 1,6 s lang). Bei reduzierter Bewegung sofort alles Mint.
 */
export function Raster({ anzahl, spalten, aktiv }: { anzahl: number; spalten: number; aktiv: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const zeilen = Math.ceil(anzahl / spalten);
  const breite = spalten * 13 - 2;
  const hoehe = zeilen * 13 - 2;
  const malen = (sekunden: number) => {
    const el = ref.current;
    const ctx = el?.getContext?.("2d");
    if (!el || !ctx) return;
    const stil = getComputedStyle(el);
    const an = stil.getPropertyValue("--mint").trim() || "#3ddc97";
    const aus = stil.getPropertyValue("--linie").trim() || "#1e3542";
    const diagonale = spalten + zeilen - 2 || 1;
    ctx.clearRect(0, 0, breite, hoehe);
    for (let i = 0; i < anzahl; i++) {
      const r = Math.floor(i / spalten);
      const c = i % spalten;
      ctx.fillStyle = sekunden >= 0.3 + ((r + c) / diagonale) * 1.6 + 0.2 ? an : aus;
      ctx.fillRect(c * 13, r * 13, 11, 11);
    }
  };
  useAblauf(
    aktiv,
    (ms) => {
      malen(ms / 1000);
      return ms < 2200;
    },
    () => malen(Number.POSITIVE_INFINITY),
    [anzahl, spalten],
  );
  return <canvas ref={ref} width={breite} height={hoehe} className={k("s5-raster")} aria-hidden="true" />;
}
