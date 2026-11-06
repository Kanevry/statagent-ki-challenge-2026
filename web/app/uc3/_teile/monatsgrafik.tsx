"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { formatZahl } from "@kic/ui/bausteine";
import { monatName } from "@/components/uc3/monat";
import { laufPfad } from "@/components/uc3/navigation";
import type { Monatslauf } from "@/components/uc3/typen";
import { bestandJeMonat, imZeitraum, zeitraumArtAus } from "@/components/uc3/zeitraum";

// Zeitreihe als Linie mit Punkten (UI-Regie v1, Abnahme 1): Balken mit abgeschnittener Achse hätten eine Schwankung
// von 2 Prozent wie ein Vielfaches aussehen lassen. Die Achse beginnt bei einem vollen Fünftausend unter dem kleinsten
// Wert, das steht unter der Kurve. Angehaltene Monate sind gelbe Punkte und tragen ihren Namen. Fährt die Maus über
// eine Spalte oder der Fokus auf einen Punkt, nennt ein Fenster Monat und Zahl; Klick öffnet den Monat. Am Handy
// eigene Maße statt einer verkleinerten Grafik, damit die Schrift lesbar bleibt. Die Linie zeichnet sich beim Laden
// und beim Umschalten einmal, bei prefers-reduced-motion nicht. Danach fällt die Animation weg: Eine Ganzseiten-
// Aufnahme startete sie sonst neu und zeigte eine fast leere Kurve.

type Masse = { breite: number; hoehe: number; links: number; rechts: number; oben: number; unten: number; schrift: number };

const DESKTOP: Masse = { breite: 960, hoehe: 264, links: 64, rechts: 12, oben: 12, unten: 28, schrift: 12 };
/** Bis dahin sind Linie (900 ms) und letzter Punkt (Verzögerung bis 900 ms, dazu 300 ms) sicher fertig. */
const ANIMATION_MS = 1_300;

const HANDY: Masse = { breite: 350, hoehe: 240, links: 8, rechts: 8, oben: 8, unten: 24, schrift: 12 };

/** Untere Achsengrenze: volles Fünftausend unter dem kleinsten Wert. */
export function achsenBeginn(werte: readonly number[]): number {
  return Math.max(0, Math.floor((Math.min(...werte) - 1) / 5_000) * 5_000);
}

/** Obere Achsengrenze: volles Fünftausend über dem größten Wert. */
export function achsenEnde(werte: readonly number[]): number {
  return Math.ceil((Math.max(...werte) + 1) / 5_000) * 5_000;
}

/** Zwei beschriftete Hilfslinien: Achsenbeginn und Achsenende. */
export function hilfslinien(beginn: number, ende: number): number[] {
  return [...new Set([beginn, ende])];
}

/**
 * Wo der Name eines angehaltenen Monats steht, ohne die Linie zu kreuzen: links über einer Spitze, unter einer Senke,
 * sonst auf der freien Seite. Werte sind die Nachbarn links und rechts; ein Monat am Rand schaut nur auf einen.
 */
export function namensLage(davor: number | undefined, wert: number, danach: number | undefined): { dx: number; dy: number; anker: "start" | "middle" | "end" } {
  const links = davor ?? danach ?? wert;
  const rechts = danach ?? davor ?? wert;
  if (links <= wert && rechts <= wert) return { dx: -10, dy: -8, anker: "end" };
  if (links >= wert && rechts >= wert) return { dx: 0, dy: 24, anker: "middle" };
  return links > wert ? { dx: 10, dy: -8, anker: "start" } : { dx: -10, dy: -8, anker: "end" };
}

function Flaeche({ monate, regelsatz, masse, className }: { monate: readonly Monatslauf[]; regelsatz: string; masse: Masse; className: string }) {
  const [aktiv, setAktiv] = useState<number | null>(null);
  const [gezeichnet, setGezeichnet] = useState(false);
  useEffect(() => {
    const zeitgeber = setTimeout(() => setGezeichnet(true), ANIMATION_MS);
    return () => clearTimeout(zeitgeber);
  }, []);
  const { breite, hoehe, links, rechts, oben, unten, schrift } = masse;
  const handy = masse === HANDY;
  const werte = monate.map((m) => m.gezaehlt);
  const beginn = achsenBeginn(werte);
  const ende = achsenEnde(werte);
  const innen = breite - links - rechts;
  const schritt = monate.length > 1 ? innen / (monate.length - 1) : innen;
  const x = (i: number) => links + (monate.length === 1 ? innen / 2 : i * schritt);
  const y = (wert: number) => oben + (1 - (wert - beginn) / (ende - beginn)) * (hoehe - oben - unten);
  const pfad = monate.map((m, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(m.gezaehlt).toFixed(1)}`).join(" ");
  const gezeigt = aktiv === null ? null : monate[aktiv];
  const lage = (i: number) => namensLage(monate[i - 1]?.gezaehlt, monate[i]!.gezaehlt, monate[i + 1]?.gezaehlt);
  const art = zeitraumArtAus(monate[0]?.zeitraumArt);

  return (
    <div className={`relative ${className}`} onMouseLeave={() => setAktiv(null)}>
      <svg
        viewBox={`0 0 ${breite} ${hoehe}`}
        className="h-auto w-full overflow-visible"
        // Gruppe statt Bild: die Punkte sind Links, und interaktive Elemente dürfen nicht in role="img" stecken (axe).
        role="group"
        aria-label={`Beschäftigungsverhältnisse ${imZeitraum(art)} von ${monatName(monate[0]!.lieferung)} bis ${monatName(monate.at(-1)!.lieferung)}, zwischen ${formatZahl(Math.min(...werte))} und ${formatZahl(Math.max(...werte))}`}
      >
        {hilfslinien(beginn, ende).map((wert) => (
          <g key={wert}>
            <line x1={links} x2={breite - rechts} y1={y(wert)} y2={y(wert)} stroke="var(--color-line)" strokeWidth={1} />
            <text
              x={handy ? links : links - 8}
              y={handy ? (wert === ende ? y(wert) + 16 : y(wert) - 6) : y(wert) + 4}
              textAnchor={handy ? "start" : "end"}
              className="fill-slate font-sans"
              fontSize={schrift}
            >
              {formatZahl(wert)}
            </text>
          </g>
        ))}
        {gezeigt && aktiv !== null && (
          <line x1={x(aktiv)} x2={x(aktiv)} y1={oben} y2={hoehe - unten} stroke="var(--color-slate)" strokeWidth={1} />
        )}
        <path className={gezeichnet ? undefined : "uc3-linie"} pathLength={1} d={pfad} fill="none" stroke="var(--color-navy)" strokeWidth={2} />
        {monate.map((m, i) => {
          const jahresanfang = m.lieferung.endsWith("-01") || i === 0;
          const name = `${monatName(m.lieferung)}: ${formatZahl(m.gezaehlt)}${m.angehalten ? ", angehalten" : ""}`;
          return (
            <Link
              key={m.lieferung}
              href={laufPfad(m.lieferung, regelsatz)}
              aria-label={name}
              className="uc3-punkt-link"
              onMouseEnter={() => setAktiv(i)}
              onFocus={() => setAktiv(i)}
              onBlur={() => setAktiv(null)}
            >
              <rect x={x(i) - schritt / 2} y={oben} width={schritt} height={hoehe - oben - unten} fill="transparent" />
              <circle
                className={gezeichnet ? undefined : "uc3-punkt"}
                style={gezeichnet ? undefined : { animationDelay: `${(i / monate.length) * 900}ms` }}
                cx={x(i)}
                cy={y(m.gezaehlt)}
                r={aktiv === i ? 7 : m.angehalten ? 6 : handy ? 3 : 4}
                fill={m.angehalten ? "var(--color-gelb)" : "var(--color-navy)"}
                stroke={m.angehalten ? "var(--color-ink)" : "none"}
                strokeWidth={m.angehalten ? 1 : 0}
              />
              {m.angehalten && aktiv !== i && (
                <text
                  x={x(i) + lage(i).dx}
                  y={y(m.gezaehlt) + lage(i).dy}
                  textAnchor={lage(i).anker}
                  className="fill-ink font-sans"
                  fontSize={schrift}
                  fontWeight={600}
                  stroke="var(--color-paper)"
                  strokeWidth={4}
                  paintOrder="stroke"
                >
                  {handy ? monatName(m.lieferung).split(" ")[0] : monatName(m.lieferung)}
                </text>
              )}
              {jahresanfang && (
                <text x={x(i)} y={hoehe - 6} textAnchor={i === 0 ? "start" : "middle"} className="fill-slate font-sans" fontSize={schrift}>
                  {handy ? m.lieferung.slice(0, 4) : monatName(m.lieferung)}
                </text>
              )}
            </Link>
          );
        })}
      </svg>
      {gezeigt && aktiv !== null && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute z-10 flex flex-col whitespace-nowrap border border-line bg-white px-3 py-2 font-sans text-14 text-ink"
          style={{
            left: `${(x(aktiv) / breite) * 100}%`,
            top: `${(y(gezeigt.gezaehlt) / hoehe) * 100}%`,
            transform: `translate(${aktiv < 4 ? "0" : aktiv > monate.length - 5 ? "-100%" : "-50%"}, calc(-100% - 12px))`,
          }}
        >
          <span className="font-semibold">{monatName(gezeigt.lieferung)}</span>
          <span className="tabular-nums">{formatZahl(gezeigt.gezaehlt)}</span>
          {gezeigt.angehalten && <span className="text-slate">angehalten</span>}
        </div>
      )}
    </div>
  );
}

export function Monatsgrafik({ monate, regelsatz, beleg }: { monate: readonly Monatslauf[]; regelsatz: string; beleg?: ReactNode }) {
  if (monate.length === 0) return null;
  const werte = monate.map((m) => m.gezaehlt);
  const art = zeitraumArtAus(monate[0]?.zeitraumArt);
  const mitHalt = monate.some((m) => m.angehalten);
  return (
    <figure className="flex flex-col gap-2">
      <style>{`
        @keyframes uc3-zeichnen { from { stroke-dashoffset: 1; } to { stroke-dashoffset: 0; } }
        @keyframes uc3-erscheinen { from { opacity: 0; } to { opacity: 1; } }
        .uc3-linie { stroke-dasharray: 1; animation: uc3-zeichnen 900ms ease-out both; }
        .uc3-punkt { animation: uc3-erscheinen 300ms ease-out both; }
        .uc3-punkt-link:focus-visible { outline: 2px solid var(--color-gruen); }
        @media (prefers-reduced-motion: reduce) { .uc3-linie, .uc3-punkt { animation: none; } }
      `}</style>
      <Flaeche monate={monate} regelsatz={regelsatz} masse={DESKTOP} className="hidden md:block" />
      <Flaeche monate={monate} regelsatz={regelsatz} masse={HANDY} className="md:hidden" />
      <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1 font-sans text-14 text-slate">
        <span className="text-ink">{bestandJeMonat(art)}</span>
        {mitHalt && (
          <span className="inline-flex items-center gap-2">
            <span aria-hidden="true" className="size-3 rounded-full border border-ink bg-gelb" />
            angehalten
          </span>
        )}
        <span>{`Die Achse beginnt bei ${formatZahl(achsenBeginn(werte))}.`}</span>
        {beleg}
      </figcaption>
    </figure>
  );
}
