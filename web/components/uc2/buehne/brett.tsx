import { akteurName, themaKurz } from "../namen";
import type { FallZustand } from "../zustand";
import { haltungWort, kategorieWort, kuerzel } from "./takt";

// Das Brett: je Thema eine Linie von "klar dagegen" bis "klar dafür", darauf ein Punkt je Gruppe. Ändert eine Gruppe
// ihre Haltung, wandert ihr Punkt sichtbar an die neue Stelle. Der Punkt der Gruppe, die gerade spricht, ist dunkel.

const STUFEN = [-2, -1, 0, 1, 2] as const;
const PUNKT = 26;

/** Letzte bekannte Haltung je Gruppe und Thema aus den bisher gezeigten Zügen. */
export function haltungen(z: FallZustand): Record<string, Record<string, number>> {
  const stand: Record<string, Record<string, number>> = {};
  for (const r of z.runden) {
    for (const [akteur, zug] of Object.entries(r.zuege)) {
      for (const t of Object.values(zug.themen)) (stand[akteur] ??= {})[t.thema] = t.haltung;
    }
  }
  return stand;
}

function kategorien(z: FallZustand): Record<string, string> {
  if (z.ergebnis) return Object.fromEntries(Object.entries(z.ergebnis.klassifikation).map(([t, k]) => [t, k.kategorie]));
  const letzte = [...z.runden].reverse().find((r) => r.ende);
  return letzte?.ende?.klassifikation ?? {};
}

export function Brett({ zustand, sprecher }: { zustand: FallZustand; sprecher: string | null }) {
  const stand = haltungen(zustand);
  const einordnung = kategorien(zustand);
  const themen = zustand.themen.length > 0 ? zustand.themen : Object.keys(einordnung).map((id) => ({ id, titel: id }));
  const gruppen = zustand.teilnehmer;

  return (
    <section aria-labelledby="brett-titel" className="flex flex-col gap-5">
      <div className="flex items-baseline justify-between">
        <h2 id="brett-titel" className="font-display text-20 font-bold text-ink">
          Wo die Gruppen stehen
        </h2>
      </div>
      <ul className="flex flex-col gap-4">
        {themen.map((thema) => {
          const hier = gruppen.filter((g) => stand[g]?.[thema.id] !== undefined);
          return (
            <li key={thema.id} className="flex flex-col gap-1">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-sans text-14 font-semibold text-ink">{themaKurz(thema.id, thema.titel)}</span>
                <span className="font-sans text-14 text-slate">{kategorieWort(einordnung[thema.id])}</span>
              </div>
              <div className="relative mx-10 h-[60px]" role="img" aria-label={beschreibung(thema.id, hier, stand, thema.titel)}>
                <div className="absolute inset-x-0 top-[13px] h-px bg-line" aria-hidden="true" />
                {STUFEN.map((s) => (
                  <div
                    key={s}
                    aria-hidden="true"
                    className="absolute top-[9px] h-2 w-px bg-line"
                    style={{ left: `${((s + 2) / 4) * 100}%` }}
                  />
                ))}
                {hier.map((g) => {
                  const h = stand[g]![thema.id]!;
                  const gleich = hier.filter((x) => stand[x]![thema.id] === h);
                  const k = gleich.indexOf(g);
                  const spalte = k % 3;
                  const zeile = Math.floor(k / 3);
                  const breite = Math.min(gleich.length, 3);
                  const dx = (spalte - (breite - 1) / 2) * (PUNKT - 2);
                  const aktiv = g === sprecher;
                  return (
                    <span
                      key={g}
                      title={`${akteurName(g)}: ${haltungWort(h)}`}
                      aria-hidden="true"
                      className={
                        "absolute flex items-center justify-center rounded-full border font-sans text-11 font-semibold " +
                        "transition-[left,top,background-color] duration-700 ease-out motion-reduce:transition-none " +
                        (aktiv ? "z-10 border-ink bg-ink text-white" : "border-line bg-white text-slate")
                      }
                      style={{
                        width: PUNKT,
                        height: PUNKT,
                        left: `calc(${((h + 2) / 4) * 100}% + ${dx - PUNKT / 2}px)`,
                        top: zeile * (PUNKT + 2),
                      }}
                    >
                      {kuerzel(g)}
                    </span>
                  );
                })}
              </div>
            </li>
          );
        })}
      </ul>
      <div className="mx-10 flex justify-between font-sans text-12 text-slate" aria-hidden="true">
        <span className="-translate-x-1/2">klar dagegen</span>
        <span>unentschieden</span>
        <span className="translate-x-1/2">klar dafür</span>
      </div>
    </section>
  );
}

function beschreibung(thema: string, gruppen: string[], stand: Record<string, Record<string, number>>, titel?: string): string {
  if (gruppen.length === 0) return `${themaKurz(thema, titel)}: noch keine Haltungen.`;
  return `${themaKurz(thema, titel)}: ${gruppen.map((g) => `${akteurName(g)} ${haltungWort(stand[g]![thema])}`).join(", ")}.`;
}
