"use client";

import { Fliesstext, Ueberschrift } from "@kic/ui/basis";
import type { WebAntrag } from "./antrag";
import { traegerName, type Traeger } from "./antwort";
import { antragLeistung, leistungName } from "./leistungen";
import { Fundstelle, OHNE_STELLE } from "./teile";

// Zuständige Stelle (#35, Urteil der Sichtprüfung): keine eigene Seite mehr, sondern die rechte Spalte von Leistungen und
// Antrag. Es steht nur, was die Daten belegt liefern: Name und Fundstelle. Adresse und Telefon liefert der Kern nicht,
// deshalb stehen sie hier nicht.

/** Eine Stelle mit allen Leistungen, für die sie zuständig ist; je Leistung die eigene Fundstelle mit eigenem Zitat. */
export interface StellenGruppe {
  name: string;
  kurz: string | null;
  leistungen: Array<Pick<Traeger, "leistung" | "fundstelle" | "zitat">>;
}

/** Stellen aus der Antwort (traeger) und aus vorbereiteten Anträgen, gleiche Stelle einmal. */
export function stellenGruppen(traeger: readonly Traeger[], antraege: readonly WebAntrag[]): StellenGruppe[] {
  const gruppen: StellenGruppe[] = [];
  const dazu = (name: string, kurz: string | null, eintrag: StellenGruppe["leistungen"][number]) => {
    let gruppe = gruppen.find((g) => g.name === name);
    if (!gruppe) {
      gruppe = { name, kurz, leistungen: [] };
      gruppen.push(gruppe);
    }
    // Dieselbe Leistung nur einmal; ein Eintrag mit Zitat ersetzt einen ohne.
    const da = gruppe.leistungen.findIndex((l) => l.leistung === eintrag.leistung && l.fundstelle === eintrag.fundstelle);
    if (da < 0) gruppe.leistungen.push(eintrag);
    else if (!gruppe.leistungen[da]?.zitat && eintrag.zitat) gruppe.leistungen[da] = eintrag;
  };
  for (const t of traeger) dazu(traegerName(t), t.stelle, { leistung: t.leistung, fundstelle: t.fundstelle, zitat: t.zitat });
  for (const a of antraege) {
    if (!a.stelle) continue;
    const leistung = antragLeistung(a.art);
    // Nennt die Antwort die Leistung schon bei dieser Stelle, kommt sie aus dem Antrag nicht doppelt dazu.
    if (gruppen.some((g) => g.name === a.stelle?.name && g.leistungen.some((l) => l.leistung === leistung))) continue;
    dazu(a.stelle.name, a.stelle.kurz ?? null, { leistung, fundstelle: a.stelle.fundstelle ?? null, zitat: a.stelle.zitat ?? null });
  }
  return gruppen;
}

export const TERMIN_SATZ = "Einen Termin vereinbaren Sie direkt bei der Stelle.";

/**
 * Kasten „Zuständige Stelle“: Name, je Leistung die Fundstelle mit Beleg, ein Satz zum Termin. Die Leistung steht
 * nur dabei, wenn die Stelle für mehrere zuständig ist.
 */
export function StelleKasten({ gruppen, als = "h2", className = "" }: { gruppen: readonly StellenGruppe[]; als?: "h2" | "h3"; className?: string }) {
  return (
    <section aria-label="Zuständige Stelle" className={`flex flex-col gap-3 rounded border border-line bg-white p-4 md:p-6 ${className}`}>
      <Ueberschrift stufe={3} als={als}>
        Zuständige Stelle
      </Ueberschrift>
      {gruppen.length === 0 ? (
        <Fliesstext groesse={14} data-uc1-ohne-stelle="">{`${OHNE_STELLE} Fragen Sie bei Ihrer Sozialversicherung nach.`}</Fliesstext>
      ) : (
        <>
          {gruppen.map((stelle) => (
            <div key={stelle.name} data-uc1-stelle="" className="flex flex-col gap-2">
              <Fliesstext className="font-semibold">{stelle.name}</Fliesstext>
              <ul className="flex flex-col gap-2" aria-label={`${stelle.name} ist zuständig für`}>
                {stelle.leistungen.map((l) => (
                  <li
                    key={`${l.leistung ?? ""}-${l.fundstelle ?? ""}`}
                    data-uc1-stelle-leistung={l.leistung ?? ""}
                    className="flex flex-col items-start gap-1"
                  >
                    {l.leistung && stelle.leistungen.length > 1 && (
                      <Fliesstext groesse={14}>{leistungName(l.leistung)}</Fliesstext>
                    )}
                    <Fundstelle fundstelle={l.fundstelle} zitat={l.zitat} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <Fliesstext groesse={14}>{TERMIN_SATZ}</Fliesstext>
        </>
      )}
    </section>
  );
}
