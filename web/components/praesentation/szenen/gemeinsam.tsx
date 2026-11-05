"use client";

import Image from "next/image";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { Folie } from "../../../lib/praesentation/folien";
import type { Inline } from "../../../lib/praesentation/markdown";
import { herkunft, screenshotKennung } from "../../../lib/praesentation/szenen-daten";
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

/**
 * Takt-Schalter für ein Element: bis Takt `ab` verborgen, danach mit Klasse `an` (startet seine Animationen).
 * Ergebnis zum Ausbreiten: `{...taktAn(2, takt)}` plus `className={k("…", an(2, takt))}`.
 */
export function taktAn(ab: number): { "data-takt": number } {
  return { "data-takt": ab };
}
export function an(ab: number, takt: number): string | false {
  return takt >= ab && "an";
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

/** Fuß: links unten die Herkunft aus dem Markdown, falls vorhanden. Zeitmarken stehen nur in den Notizen. */
export function Fuss({ folie }: { folie: Folie }) {
  const quelle = herkunft(folie);
  return quelle ? <p className={k("herkunft")}>{quelle}</p> : null;
}

/**
 * Kreis einer Aufgabe (1, 2, 3) oder der gefüllte Kreis 4. Mit `flip` (Standard) trägt er `data-k` und gleitet beim
 * Szenenwechsel von der alten an die neue Stelle (schau.tsx). Position und Größe in px, `t` = Auftritt in Sekunden,
 * `ab` = erst ab diesem Takt sichtbar.
 */
export function Kreis({
  n,
  x,
  y,
  d,
  t,
  klasse,
  flip = true,
  ab,
  takt = 0,
}: {
  n: number;
  x: number;
  y: number;
  d: number;
  t?: number;
  klasse?: string;
  flip?: boolean;
  ab?: number;
  takt?: number;
}) {
  return (
    <div
      className={k("kreis", `k${n}`, klasse, ab !== undefined && an(ab, takt))}
      {...(flip ? { "data-k": n } : {})}
      {...(ab !== undefined ? taktAn(ab) : {})}
      style={vars({ x: `${x}px`, y: `${y}px`, d: `${d}px`, ...(t === undefined ? {} : { t }) })}
    >
      <div className={k("kreis-koerper")} aria-hidden="true">
        {n}
      </div>
    </div>
  );
}

/**
 * Kopf der Szenen 3 bis 9: kleiner Kreis 3 links, Titel eine Zeile daneben. Über dem Kreis steht klein „Use Case 3“,
 * damit die 3 nicht als Foliennummer gelesen wird (Sans, normale Schreibung, kein Versal- oder Mono-Etikett, #59).
 */
export function Kopf({ titel, lang = false, t = 0.1 }: { titel: string; lang?: boolean; t?: number }) {
  return (
    <>
      <p className={k("kopf-uc", "a")} style={vars({ t })}>
        Use Case 3
      </p>
      <Kreis n={3} x={120} y={92} d={72} />
      <h2 className={k("titel", (lang || titel.length > 52) && "titel-lang", "a")} style={vars({ t })}>
        {titel}
      </h2>
    </>
  );
}

/** Gezeichneter Mint-Haken (SVG mit pathLength 1). */
export function Haken({ klasse, viewBox, d, t, dauer }: { klasse?: string; viewBox: string; d: string; t: number; dauer?: number }) {
  return (
    <svg className={k(klasse, "haken")} viewBox={viewBox} aria-hidden="true">
      <path className={k("strich", "zeichnet")} style={vars({ t, ...(dauer ? { dauer: `${dauer}s` } : {}) })} pathLength={1} d={d} />
    </svg>
  );
}

/**
 * Gelbes Pause-Zeichen für einen angehaltenen Monat (Szenen 3 und 5): gleiche Bildsprache, Klasse `pause`. Mit `t`
 * zeichnen sich die Striche beim Betreten (Sekunden), ohne `t` steuert die Szene den Auftritt selbst.
 */
export function Pause({ klasse, t, dauer }: { klasse?: string; t?: number; dauer?: number }) {
  return (
    <svg className={k(klasse, "pause")} viewBox="0 0 40 36" aria-hidden="true">
      <path
        className={k("strich", t !== undefined && "zeichnet")}
        style={t === undefined ? undefined : vars({ t, ...(dauer ? { dauer: `${dauer}s` } : {}) })}
        pathLength={1}
        d="M15 9v18M25 9v18"
      />
    </svg>
  );
}

/**
 * Blick in die App: ruhiges Fenster mit einer echten Aufnahme aus bilder.ts, ab Takt `ab`. Ohne Bild zur Kennung aus
 * `screenshot:` erscheint nichts. Der Alt-Text steht im Frontmatter unter `bild_alt`.
 */
export function Blick({ folie, ab, takt, tt, lage }: { folie: Folie; ab: number; takt: number; tt: number; lage: CSSProperties }) {
  const bild = bildFuer(screenshotKennung(folie));
  if (!bild) return null;
  return (
    <figure className={k("blick", an(ab, takt))} {...taktAn(ab)} style={{ ...lage, ...vars({ tt }) }}>
      <Image src={bild} alt={folie.daten.bild_alt ?? folie.titel} fill sizes={`${String(lage.width ?? 600)}px`} unoptimized />
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

/** Zählt beim Betreten von 0 auf `ziel` (`dauer` ms ab `start` ms). Ohne JavaScript und bei reduzierter Bewegung: Endwert. */
export function Zaehler({ ziel, aktiv, start = 0, dauer = 1200, className }: { ziel: number; aktiv: boolean; start?: number; dauer?: number; className?: string }) {
  const [wert, setWert] = useState(ziel);
  useAblauf(
    aktiv && Number.isFinite(ziel),
    (ms) => {
      const p = Math.max(0, Math.min(1, (ms - start) / dauer));
      setWert(Math.round(ziel * (1 - Math.pow(1 - p, 3))));
      return p < 1;
    },
    () => setWert(ziel),
    [ziel, start, dauer],
  );
  return <span className={className}>{Number.isFinite(wert) ? FORMAT.format(wert) : ""}</span>;
}

/**
 * Tippt `text` beim Betreten Zeichen für Zeichen (`ms` je Zeichen, ab `start` ms). Der ganze Text steht immer im
 * DOM; der noch nicht getippte Rest ist nur unsichtbar, damit die Zeile nicht springt. Vorgelesen wird nur der
 * ganze Text (sr-only), die getippten Teile sind aria-hidden. Der Rahmen braucht kein aria-label.
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
      <span className="sr-only">{text}</span>
      <span aria-hidden="true">{text.slice(0, n)}</span>
      <span className={k("rest")} aria-hidden="true">
        {text.slice(n)}
      </span>
    </>
  );
}

/**
 * Raster aus `anzahl` Quadraten (`zelle` px, Abstand `luecke` px) als Canvas, Farbe aus der CSS-Variable `farbe`.
 * Mit `welle` füllt sich jede Spalte erst, wenn die Vergleichslinie sie erreicht (`start` bis `start + dauer` s);
 * vorher ist sie in `--linie`. Bei reduzierter Bewegung sofort fertig. Keine Schleife nach dem Ende.
 */
export function Raster({
  anzahl,
  spalten,
  zelle,
  luecke,
  farbe,
  aktiv,
  welle,
}: {
  anzahl: number;
  spalten: number;
  zelle: number;
  luecke: number;
  farbe: "--mint" | "--neben";
  aktiv: boolean;
  welle?: { start: number; dauer: number };
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const zeilen = Math.ceil(anzahl / spalten);
  const schritt = zelle + luecke;
  const breite = spalten * schritt - luecke;
  const hoehe = zeilen * schritt - luecke;
  const malen = (sekunden: number) => {
    const el = ref.current;
    const ctx = el?.getContext?.("2d");
    if (!el || !ctx) return;
    const stil = getComputedStyle(el);
    const voll = stil.getPropertyValue(farbe).trim() || "#3ddc97";
    const leer = stil.getPropertyValue("--linie").trim() || "#1e3542";
    ctx.clearRect(0, 0, breite, hoehe);
    for (let i = 0; i < anzahl; i++) {
      const c = i % spalten;
      const erreicht = !welle || sekunden >= welle.start + (c / spalten) * welle.dauer + 0.2;
      ctx.fillStyle = erreicht ? voll : leer;
      ctx.fillRect(c * schritt, Math.floor(i / spalten) * schritt, zelle, zelle);
    }
  };
  useAblauf(
    aktiv && welle !== undefined,
    (ms) => {
      malen(ms / 1000);
      return welle !== undefined && ms < (welle.start + welle.dauer + 0.4) * 1000;
    },
    () => malen(Number.POSITIVE_INFINITY),
    [anzahl, spalten, zelle, luecke, farbe],
  );
  return <canvas ref={ref} width={breite} height={hoehe} aria-hidden="true" />;
}
