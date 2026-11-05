"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { Folie } from "../../../lib/praesentation/folien";
import type { Inline } from "../../../lib/praesentation/markdown";
import { herkunft, zeitZeile } from "../../../lib/praesentation/szenen-daten";
import stile from "../szenen.module.css";

// Achtung: aus lib/praesentation/folien.ts nur Typen importieren. Die Datei lädt node:fs und darf nicht in den Browser.

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

/** Was jede Szene bekommt: die geparste Folie, ob sie gerade läuft, und den gezeigten Takt (0 = noch keiner). */
export interface SzeneProps {
  folie: Folie;
  nr: number;
  aktiv: boolean;
  takt: number;
}

const S = stile as Record<string, string | undefined>;

/** Klassen aus dem CSS-Modul; `false` und unbekannte Namen fallen weg. */
export function k(...namen: (string | false | undefined)[]): string {
  return namen
    .filter((n): n is string => typeof n === "string" && n !== "")
    .map((n) => S[n] ?? n)
    .join(" ");
}

/** Staffel `--i` und weitere CSS-Variablen als Style-Objekt. */
export function vars(werte: Record<string, string | number>): CSSProperties {
  return Object.fromEntries(Object.entries(werte).map(([n, v]) => [`--${n}`, String(v)])) as CSSProperties;
}

const FORMAT = new Intl.NumberFormat("de-DE");

/** Nutzer wünscht reduzierte Bewegung. Auf dem Server und vor dem ersten Effekt: nein. */
export function istRuhig(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

/** Fußzeile: links die Herkunft aus dem Markdown, rechts Nummer und Zeit. */
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
 * Zählt beim Betreten der Szene von 0 auf `ziel` hoch (1,2 s, requestAnimationFrame). Ohne JavaScript, im Druck
 * und bei reduzierter Bewegung steht sofort der Endwert da.
 */
export function Zaehler({ ziel, aktiv, className }: { ziel: number; aktiv: boolean; className?: string }) {
  const [wert, setWert] = useState(ziel);
  useEffect(() => {
    if (!aktiv || istRuhig() || !Number.isFinite(ziel)) {
      setWert(ziel);
      return;
    }
    let t0: number | null = null;
    let id = 0;
    const schritt = (t: number) => {
      t0 ??= t;
      const p = Math.min(1, (t - t0) / 1200);
      setWert(Math.round(ziel * (1 - Math.pow(1 - p, 3))));
      if (p < 1) id = requestAnimationFrame(schritt);
    };
    setWert(0);
    id = requestAnimationFrame(schritt);
    return () => cancelAnimationFrame(id);
  }, [aktiv, ziel]);
  return <span className={className}>{Number.isFinite(wert) ? FORMAT.format(wert) : ""}</span>;
}

/**
 * Tippt `text` beim Betreten Zeichen für Zeichen (32 ms je Zeichen, requestAnimationFrame). Der ganze Text steht
 * immer im DOM; der noch nicht getippte Rest ist nur unsichtbar, damit die Zeile nicht springt.
 */
export function Getippt({ text, aktiv, start = 0 }: { text: string; aktiv: boolean; start?: number }) {
  const [n, setN] = useState(text.length);
  useEffect(() => {
    if (!aktiv || istRuhig()) {
      setN(text.length);
      return;
    }
    let t0: number | null = null;
    let id = 0;
    const schritt = (t: number) => {
      t0 ??= t;
      const zeichen = Math.max(0, Math.floor((t - t0 - start) / 32));
      setN(Math.min(text.length, zeichen));
      if (zeichen < text.length) id = requestAnimationFrame(schritt);
    };
    setN(0);
    id = requestAnimationFrame(schritt);
    return () => cancelAnimationFrame(id);
  }, [aktiv, text, start]);
  return (
    <>
      <span>{text.slice(0, n)}</span>
      <span className={k("s10-rest")} aria-hidden="true">
        {text.slice(n)}
      </span>
    </>
  );
}

/**
 * Raster aus `anzahl` Quadraten (11 px, Abstand 2 px) als Canvas. Beim Betreten leuchtet eine Welle von links oben
 * nach rechts unten Mint auf (2 s). Bei reduzierter Bewegung sofort alles Mint. Keine Schleife nach dem Ende.
 */
export function Raster({ anzahl, spalten, aktiv }: { anzahl: number; spalten: number; aktiv: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const zeilen = Math.ceil(anzahl / spalten);
  const breite = spalten * 13 - 2;
  const hoehe = zeilen * 13 - 2;
  useEffect(() => {
    const el = ref.current;
    const ctx = el?.getContext("2d");
    if (!el || !ctx) return;
    const stil = getComputedStyle(el);
    const an = stil.getPropertyValue("--mint").trim() || "rgb(61 220 151)";
    const aus = stil.getPropertyValue("--linie").trim() || "rgb(30 53 66)";
    const diagonale = spalten + zeilen - 2 || 1;
    const malen = (sekunden: number) => {
      ctx.clearRect(0, 0, breite, hoehe);
      for (let i = 0; i < anzahl; i++) {
        const r = Math.floor(i / spalten);
        const c = i % spalten;
        const start = ((r + c) / diagonale) * 1.6;
        ctx.fillStyle = sekunden >= start + 0.2 ? an : aus;
        ctx.fillRect(c * 13, r * 13, 11, 11);
      }
    };
    if (!aktiv || istRuhig()) {
      malen(Number.POSITIVE_INFINITY);
      return;
    }
    let t0: number | null = null;
    let id = 0;
    const schritt = (t: number) => {
      t0 ??= t;
      const s = (t - t0) / 1000;
      malen(s);
      if (s < 2) id = requestAnimationFrame(schritt);
      else malen(Number.POSITIVE_INFINITY);
    };
    id = requestAnimationFrame(schritt);
    return () => cancelAnimationFrame(id);
  }, [aktiv, anzahl, spalten, zeilen, breite, hoehe]);
  return <canvas ref={ref} width={breite} height={hoehe} className={k("s5-raster")} aria-hidden="true" />;
}
