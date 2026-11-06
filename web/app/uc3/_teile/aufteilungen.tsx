import type { ReactNode } from "react";
import { formatZahl } from "@kic/ui/bausteine";
import { laufBeleg } from "@/components/uc3/beleg";
import { BelegLink } from "@/components/uc3/beleg-link";
import { balkenProzent, sqlGeschlecht, type Gruppe } from "@/components/uc3/dashboard";
import { sqlRegionen, type Region } from "@/components/uc3/lauf-detail";
import { monatName } from "@/components/uc3/monat";
import type { Lauf } from "@/components/uc3/typen";
import { imZeitraum, zeitraumArtAus } from "@/components/uc3/zeitraum";

// Die Aufteilungen, nach denen die Jury fragt, im letzten Monat. Tabelle mit echtem Kopf; der Balken beginnt bei null
// und ist nur Zusatz zur Zahl.

const kopf = "sr-only";

function Balken({ titel, reihen, beleg }: { titel: string; reihen: readonly Pick<Gruppe, "code" | "name" | "anzahl">[]; beleg: ReactNode }) {
  const groesste = Math.max(0, ...reihen.map((r) => r.anzahl));
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4">
        <h3 className="font-sans text-14 font-medium text-slate">{titel}</h3>
        {beleg}
      </div>
      <table className="w-full border-collapse font-sans text-14 text-ink">
        <caption className="sr-only">{titel}</caption>
        <thead>
          <tr>
            <th scope="col" className={kopf}>{titel}</th>
            <th scope="col" className={kopf}>Beschäftigungsverhältnisse</th>
            <th scope="col" className={kopf}>Balken</th>
          </tr>
        </thead>
        <tbody>
          {reihen.map((r) => (
            <tr key={r.code} className="border-b border-line">
              <th scope="row" className="py-1.5 pr-3 text-left font-normal whitespace-nowrap">{r.name}</th>
              <td className="py-1.5 pr-3 text-right tabular-nums">{formatZahl(r.anzahl)}</td>
              <td className="w-full py-1.5" aria-hidden="true">
                <div className="h-2 bg-navy" style={{ width: `${balkenProzent(r.anzahl, groesste)}%` }} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Aufteilungen({ lauf, regionen, geschlecht }: { lauf: Lauf; regionen: readonly Region[]; geschlecht: readonly Gruppe[] }) {
  const wann = imZeitraum(zeitraumArtAus(lauf.zeitraumArt));
  return (
    <section aria-labelledby="aufteilung-titel" className="flex flex-col gap-3">
      <h2 id="aufteilung-titel" className="font-sans text-16 font-semibold text-ink">
        {`${monatName(lauf.lieferung)} aufgeteilt, Beschäftigungsverhältnisse ${wann}`}
      </h2>
      <div className="grid gap-x-12 gap-y-6 lg:grid-cols-[3fr_2fr]">
        <Balken titel="Nach Bundesland" reihen={regionen} beleg={<BelegLink {...laufBeleg(lauf, { sql: sqlRegionen(lauf) })} />} />
        <Balken titel="Nach Geschlecht" reihen={geschlecht} beleg={<BelegLink {...laufBeleg(lauf, { sql: sqlGeschlecht(lauf) })} />} />
      </div>
    </section>
  );
}
