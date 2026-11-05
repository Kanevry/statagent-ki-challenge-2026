import Link from "next/link";
import { formatZahl } from "@kic/ui/bausteine";
import { monatName } from "@/components/uc3/monat";
import { laufPfad } from "@/components/uc3/navigation";
import type { Monatslauf } from "@/components/uc3/typen";

// Zeitreihe als Linie mit Punkten (UI-Regie v1, Abnahme 1): Balken mit abgeschnittener Achse hätten eine Schwankung
// von 2 Prozent wie ein Vielfaches aussehen lassen. Die Achse beginnt bei einem vollen Zehntausend unter dem
// kleinsten Wert und ist mit zwei Hilfslinien beschriftet. Angehaltene Monate sind gelbe Punkte; Hover nennt Monat
// und Zahl, Klick öffnet den Monat. Die Linie zeichnet sich beim Laden einmal, bei prefers-reduced-motion nicht.

const HOEHE = 200;
const BREITE = 960;
const LINKS = 64;
const OBEN = 12;
const UNTEN = 28;

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

export function Monatsgrafik({ monate, regelsatz }: { monate: readonly Monatslauf[]; regelsatz: string }) {
  if (monate.length === 0) return null;
  const werte = monate.map((m) => m.gezaehlt);
  const beginn = achsenBeginn(werte);
  const ende = achsenEnde(werte);
  const innen = BREITE - LINKS - 8;
  const x = (i: number) => LINKS + (monate.length === 1 ? innen / 2 : (i / (monate.length - 1)) * innen);
  const y = (wert: number) => OBEN + (1 - (wert - beginn) / (ende - beginn)) * (HOEHE - OBEN - UNTEN);
  const pfad = monate.map((m, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(m.gezaehlt).toFixed(1)}`).join(" ");

  return (
    <figure className="flex flex-col">
      <style>{`
        @keyframes uc3-zeichnen { from { stroke-dashoffset: 1; } to { stroke-dashoffset: 0; } }
        @keyframes uc3-erscheinen { from { opacity: 0; } to { opacity: 1; } }
        .uc3-linie { stroke-dasharray: 1; animation: uc3-zeichnen 900ms ease-out both; }
        .uc3-punkt { animation: uc3-erscheinen 300ms ease-out both; }
        .uc3-punkt-link:hover .uc3-punkt, .uc3-punkt-link:focus-visible .uc3-punkt { r: 7; }
        @media (prefers-reduced-motion: reduce) { .uc3-linie, .uc3-punkt { animation: none; } }
      `}</style>
      <svg
        viewBox={`0 0 ${BREITE} ${HOEHE + 36}`}
        className="h-auto w-full"
        role="img"
        aria-label={`Beschäftigungsverhältnisse am Stichtag von ${monatName(monate[0]!.lieferung)} bis ${monatName(monate.at(-1)!.lieferung)}, zwischen ${formatZahl(Math.min(...werte))} und ${formatZahl(Math.max(...werte))}`}
      >
        {hilfslinien(beginn, ende).map((wert) => (
          <g key={wert}>
            <line x1={LINKS} x2={BREITE - 8} y1={y(wert)} y2={y(wert)} stroke="var(--color-line)" strokeWidth={1} />
            <text x={LINKS - 8} y={y(wert) + 4} textAnchor="end" className="hidden fill-slate font-sans md:inline" fontSize={12}>
              {formatZahl(wert)}
            </text>
            <text x={LINKS + 4} y={wert === ende ? y(wert) + 30 : y(wert) - 8} textAnchor="start" className="fill-slate font-sans md:hidden" fontSize={30}>
              {formatZahl(wert)}
            </text>
          </g>
        ))}
        <path className="uc3-linie" pathLength={1} d={pfad} fill="none" stroke="var(--color-navy)" strokeWidth={2} />
        {monate.map((m, i) => {
          const jahresanfang = m.lieferung.endsWith("-01") || i === 0;
          return (
            <Link key={m.lieferung} href={laufPfad(m.lieferung, regelsatz)} className="uc3-punkt-link">
              <title>{`${monatName(m.lieferung)}: ${formatZahl(m.gezaehlt)}${m.angehalten ? ", angehalten" : ""}`}</title>
              <circle cx={x(i)} cy={y(m.gezaehlt)} r={14} fill="transparent" />
              <circle
                className="uc3-punkt"
                style={{ animationDelay: `${(i / monate.length) * 900}ms` }}
                cx={x(i)}
                cy={y(m.gezaehlt)}
                r={m.angehalten ? 6 : 4}
                fill={m.angehalten ? "var(--color-gelb)" : "var(--color-navy)"}
                stroke={m.angehalten ? "var(--color-ink)" : "none"}
                strokeWidth={m.angehalten ? 1 : 0}
              />
              {jahresanfang && (
                <>
                  <text x={x(i)} y={HOEHE - 6} textAnchor={i === 0 ? "start" : "middle"} className="hidden fill-slate font-sans md:inline" fontSize={12}>
                    {monatName(m.lieferung)}
                  </text>
                  <text x={x(i)} y={HOEHE + 30} textAnchor={i === 0 ? "start" : "middle"} className="fill-slate font-sans md:hidden" fontSize={30}>
                    {m.lieferung.slice(0, 4)}
                  </text>
                </>
              )}
            </Link>
          );
        })}
      </svg>
    </figure>
  );
}
