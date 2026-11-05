import { formatZahl } from "@kic/ui/bausteine";
import type { Region } from "@/components/uc3/lauf-detail";

const kopf = "border-b border-ink py-2 pr-4 text-left align-bottom font-sans text-12 font-semibold text-slate";
const zelle = "py-2 pr-4 align-top font-sans text-14 text-ink";
const zahlZelle = `${zelle} text-right tabular-nums`;

/** Bestand je Bundesland mit Summenzeile. Ab 768 px eine Tabelle, darunter eine Liste mit denselben Angaben. */
export function Bundeslaender({ regionen, stichtag }: { regionen: readonly Region[]; stichtag: string }) {
  const summe = regionen.reduce((s, r) => s + r.anzahl, 0);
  return (
    <>
      <table className="hidden w-full max-w-xl border-collapse md:table">
        <caption className="sr-only">{`Beschäftigungsverhältnisse am ${stichtag} je Bundesland`}</caption>
        <thead>
          <tr>
            <th scope="col" className={kopf}>
              Bundesland
            </th>
            <th scope="col" className={`${kopf} pr-0 text-right`}>
              Beschäftigungsverhältnisse
            </th>
          </tr>
        </thead>
        <tbody>
          {regionen.map((r) => (
            <tr key={r.code} className="border-b border-line">
              <th scope="row" className={`${zelle} text-left font-normal`}>
                {r.name}
              </th>
              <td className={`${zahlZelle} pr-0`}>{formatZahl(r.anzahl)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row" className={`${zelle} text-left font-semibold`}>
              Österreich gesamt
            </th>
            <td className={`${zahlZelle} pr-0 font-semibold`}>{formatZahl(summe)}</td>
          </tr>
        </tfoot>
      </table>

      <ul className="flex flex-col md:hidden" aria-label="Bundesländer">
        {regionen.map((r) => (
          <li key={r.code} className="flex items-baseline justify-between gap-4 border-b border-line py-2">
            <span className="font-sans text-14 text-ink">{r.name}</span>
            <span className="font-mono text-14 tabular-nums text-ink">{formatZahl(r.anzahl)}</span>
          </li>
        ))}
        <li className="flex items-baseline justify-between gap-4 py-2">
          <span className="font-sans text-14 font-semibold text-ink">Österreich gesamt</span>
          <span className="font-mono text-14 font-semibold tabular-nums text-ink">{formatZahl(summe)}</span>
        </li>
      </ul>
    </>
  );
}
