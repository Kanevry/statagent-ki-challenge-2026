import Link from "next/link";
import { Ueberschrift } from "@kic/ui/basis";
import { formatZahl, HerkunftChip } from "@kic/ui/bausteine";
import { sqlPruefungMalMonat, type PruefungMalMonat } from "@/components/uc3/bericht";
import { GRUPPEN, gruppeAus, gruppeVon } from "@/components/uc3/einstufung-gruppen";
import { pruefungTitel } from "@/components/uc3/lauf-detail";
import { monatName } from "@/components/uc3/monat";
import { berichtPfad } from "@/components/uc3/navigation";

const MONATE_KURZ = ["Jän", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];

const rand = "border-b border-line";
const zahlZelle = `${rand} px-1 py-1 text-right align-top font-mono text-12 tabular-nums`;
// Deckend, damit beim seitlichen Scrollen nichts durchscheint; schmal, damit am Handy die Zahlen Platz haben.
const ersteSpalte = `sticky left-0 z-10 w-40 min-w-40 bg-paper py-1 pr-2 text-left align-top font-sans text-12 md:w-64 md:min-w-64 md:text-14`;
// Direkt nach der Prüfung: Auf 1440 scrollen die letzten Monate seitlich, die Summen bleiben trotzdem im Blick.
const summe = "px-1 py-1 pr-3 text-right align-top font-mono text-12 font-semibold tabular-nums text-ink";

function Spaltenkopf({ lieferung, regelsatz }: { lieferung: string; regelsatz: string }) {
  const [jahr, monat] = lieferung.split("-");
  return (
    <th scope="col" className="border-b border-ink px-1 py-1 text-right align-bottom font-sans text-12 font-semibold text-slate">
      <Link href={berichtPfad(lieferung, regelsatz)} aria-label={monatName(lieferung)} className="block whitespace-nowrap underline-offset-4 hover:underline">
        {MONATE_KURZ[Number(monat) - 1]}
        <br />
        {jahr?.slice(2)}
      </Link>
    </th>
  );
}

/** Tabelle Prüfung mal Monat (Bewertungsraster: „erkennt alle Fehler“): alle Auffälligkeiten auf einen Blick. */
export function PruefungMalMonatTabelle({ daten, monate, regelsatz }: { daten: PruefungMalMonat; monate: readonly string[]; regelsatz: string }) {
  const summenSatz = GRUPPEN.map((g) => `${formatZahl(daten.summen[g.art].gesamt)} ${g.kurz}`).join(", ");
  const monateText = monate.length === 1 ? "einem Monat" : `${formatZahl(monate.length)} Monaten`;
  return (
    <section aria-labelledby="pruefungen-titel" className="flex min-w-0 flex-col gap-4">
      <Ueberschrift stufe={3} als="h2" id="pruefungen-titel">
        {`${formatZahl(daten.gesamt)} Auffälligkeiten in ${monateText}: ${summenSatz}.`}
      </Ueberschrift>
      <HerkunftChip quelle="meta.pruefung_treffer" sql={sqlPruefungMalMonat(regelsatz)} />
      <ul className="flex flex-col gap-1 font-sans text-14 text-ink" aria-label="Zeichen in der Tabelle">
        {GRUPPEN.map((g) => (
          <li key={g.art}>
            <span aria-hidden="true" className={`inline-block w-5 font-semibold ${g.farbe}`}>
              {g.zeichen}
            </span>
            {`${g.titel} (im Bericht: ${g.vorlage})`}
          </li>
        ))}
      </ul>
      <p className="max-w-3xl font-sans text-14 text-slate">
        Jede Zahl sagt, wie viel die Prüfung in diesem Monat gefunden hat: Zeilen, Beschäftigungsverhältnisse oder Gruppen. Die Summe zählt die Auffälligkeiten, also je Prüfung die Monate mit einem Fund. Ein Klick öffnet den Bericht des Monats.
      </p>
      <div className="overflow-x-auto" role="region" aria-labelledby="pruefungen-titel" tabIndex={0}>
        <table className="border-collapse">
          <caption className="sr-only">Auffälligkeiten je Prüfung und Monat mit Anzahl und Einstufung</caption>
          <thead>
            <tr>
              <th scope="col" className={`${ersteSpalte} border-b border-ink align-bottom font-semibold text-slate`}>
                Prüfung
              </th>
              <th scope="col" className="border-b border-ink px-1 py-1 pr-3 text-right align-bottom font-sans text-12 font-semibold text-slate">
                Summe
              </th>
              {monate.map((m) => (
                <Spaltenkopf key={m} lieferung={m} regelsatz={regelsatz} />
              ))}
            </tr>
          </thead>
          <tbody>
            {daten.zeilen.map((z) => (
              <tr key={z.name} data-regel={z.name}>
                <th scope="row" className={`${ersteSpalte} ${rand} font-normal text-ink`}>
                  {pruefungTitel(z.name)}
                  <span className="text-slate">{` (${z.name.split("_")[0]})`}</span>
                </th>
                <td className={`${summe} ${rand}`}>{formatZahl(Object.keys(z.zellen).length)}</td>
                {monate.map((m) => {
                  const zelle = z.zellen[m];
                  if (!zelle) return <td key={m} className={zahlZelle} />;
                  const gruppe = gruppeVon(gruppeAus(zelle.einstufung));
                  return (
                    <td key={m} className={zahlZelle}>
                      <Link
                        href={`${berichtPfad(m, regelsatz)}#auffaelligkeiten`}
                        aria-label={`${monatName(m)}: ${formatZahl(zelle.anzahl)}, ${gruppe.titel}${zelle.anhalten ? ", hält den Monat an" : ""}`}
                        className={`block min-h-6 whitespace-nowrap underline-offset-2 hover:underline ${gruppe.farbe} ${zelle.anhalten ? "font-semibold" : ""}`}
                      >
                        <span aria-hidden="true">{gruppe.zeichen}</span>
                        <br />
                        {formatZahl(zelle.anzahl)}
                      </Link>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
          <tfoot>
            {GRUPPEN.map((g) => (
              <tr key={g.art}>
                <th scope="row" className={`${ersteSpalte} ${rand} font-normal text-ink`}>
                  <span aria-hidden="true" className={`inline-block w-5 font-semibold ${g.farbe}`}>
                    {g.zeichen}
                  </span>
                  {g.titel}
                </th>
                <td className={`${summe} ${rand}`}>{formatZahl(daten.summen[g.art].gesamt)}</td>
                {monate.map((m) => (
                  <td key={m} className={`${zahlZelle} text-ink`}>
                    {formatZahl(daten.summen[g.art].jeMonat[m] ?? 0)}
                  </td>
                ))}
              </tr>
            ))}
            <tr>
              <th scope="row" className={`${ersteSpalte} border-t border-ink font-semibold text-ink`}>
                Auffälligkeiten
              </th>
              <td className={`${summe} border-t border-ink`}>{formatZahl(daten.gesamt)}</td>
              {monate.map((m) => (
                <td key={m} className="border-t border-ink px-1 py-1 text-right font-mono text-12 font-semibold tabular-nums text-ink">
                  {formatZahl(daten.jeMonat[m] ?? 0)}
                </td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
