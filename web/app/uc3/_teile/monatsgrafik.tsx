import Link from "next/link";
import { formatZahl } from "@kic/ui/bausteine";
import { monatName } from "@/components/uc3/monat";
import { laufPfad } from "@/components/uc3/navigation";
import type { Monatslauf } from "@/components/uc3/typen";

// 24 Balken, ein Balken je Monat (UI-Regie v1): angehaltene Monate gelb, Hover nennt Monat und Zahl, Klick öffnet
// den Monat. Die Achse beginnt nicht bei null, weil sich der Bestand nur um wenige Prozent bewegt; das steht als
// Satz unter der Grafik. Die Balken wachsen beim Laden einmal, bei prefers-reduced-motion stehen sie still.

const HOEHE = 200;
const BREITE = 960;
const LUECKE = 6;

/** Achsenbeginn: nächstes volles Zehntausend unter dem kleinsten Wert, mit etwas Luft. */
export function achsenBeginn(werte: readonly number[]): number {
  const min = Math.min(...werte);
  return Math.max(0, Math.floor((min * 0.99) / 10_000) * 10_000);
}

export function Monatsgrafik({ monate, regelsatz }: { monate: readonly Monatslauf[]; regelsatz: string }) {
  if (monate.length === 0) return null;
  const werte = monate.map((m) => m.gezaehlt);
  const beginn = achsenBeginn(werte);
  const max = Math.max(...werte);
  const spanne = Math.max(1, max - beginn);
  const breite = (BREITE - LUECKE * (monate.length - 1)) / monate.length;

  return (
    <figure className="flex flex-col gap-2">
      <style>{`
        @keyframes uc3-wachsen { from { transform: scaleY(0); } to { transform: scaleY(1); } }
        .uc3-balken { transform-box: fill-box; transform-origin: bottom; animation: uc3-wachsen 700ms ease-out both; }
        .uc3-balken-link:hover .uc3-balken, .uc3-balken-link:focus-visible .uc3-balken { opacity: 1; }
        @media (prefers-reduced-motion: reduce) { .uc3-balken { animation: none; } }
      `}</style>
      <svg
        viewBox={`0 0 ${BREITE} ${HOEHE + 24}`}
        className="h-auto w-full"
        role="img"
        aria-label={`Beschäftigungsverhältnisse am Stichtag von ${monatName(monate[0]!.lieferung)} bis ${monatName(monate.at(-1)!.lieferung)}`}
      >
        {monate.map((m, i) => {
          const h = Math.max(4, ((m.gezaehlt - beginn) / spanne) * (HOEHE - 8));
          const x = i * (breite + LUECKE);
          const jahresanfang = m.lieferung.endsWith("-01") || i === 0;
          return (
            <Link key={m.lieferung} href={laufPfad(m.lieferung, regelsatz)} className="uc3-balken-link">
              <title>{`${monatName(m.lieferung)}: ${formatZahl(m.gezaehlt)}${m.angehalten ? ", angehalten" : ""}`}</title>
              <rect
                className="uc3-balken"
                style={{ animationDelay: `${i * 25}ms`, opacity: m.angehalten ? 1 : 0.55 }}
                x={x}
                y={HOEHE - h}
                width={breite}
                height={h}
                rx={2}
                fill={m.angehalten ? "var(--color-gelb)" : "var(--color-navy)"}
              />
              {jahresanfang && (
                <text x={x} y={HOEHE + 18} className="fill-slate font-sans" fontSize={13}>
                  {monatName(m.lieferung)}
                </text>
              )}
            </Link>
          );
        })}
      </svg>
      <figcaption className="font-sans text-12 text-slate">
        {`Ein Balken je Monat, gelb: angehalten. Die Achse beginnt bei ${formatZahl(beginn)}.`}
      </figcaption>
    </figure>
  );
}
