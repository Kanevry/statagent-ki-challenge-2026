import { formatZahl } from "@kic/ui/bausteine";
import type { AbschnittBestand, AbschnittVergleich, AbschnittZeile } from "@/components/uc3/klassifikation";

const kopf = "border-b border-ink py-2 pr-4 text-left align-bottom font-sans text-12 font-semibold text-slate";
const zelle = "py-2 pr-4 align-top font-sans text-14 text-ink";
const zahlZelle = `${zelle} text-right font-mono tabular-nums`;

/** Vergleich in einfachen Worten. */
function vergleichWort(vergleich: AbschnittVergleich | null): string {
  if (!vergleich) return "entfällt";
  switch (vergleich.art) {
    case "gleich":
      return "gleich";
    case "verschoben":
      return `war 2008 ${vergleich.vonCode}`;
    case "neu":
      return "neu zugeschnitten";
  }
}

function Vergleich({ vergleich }: { vergleich: AbschnittVergleich | null }) {
  const betont = vergleich?.art === "neu";
  return <span className={betont ? "font-semibold text-warn-fg" : "text-ink"}>{vergleichWort(vergleich)}</span>;
}

function wertVon(bestand: readonly AbschnittBestand[] | null, version: string, code: string): number | null {
  if (!bestand) return null;
  return bestand.find((b) => b.version === version && b.code === code)?.wert ?? null;
}

function Wert({ wert }: { wert: number | null }) {
  return wert === null ? <span className="font-sans text-12 text-slate">keiner</span> : <>{formatZahl(wert)}</>;
}

/**
 * Ein Buchstabe je Zeile, 2008 neben 2025. So sieht man, dass derselbe Buchstabe ab Jänner 2025 eine andere Branche
 * meinen kann. Ab 768 px eine Tabelle, darunter eine Liste mit denselben Angaben.
 */
export function Abschnittstabelle({
  zeilen,
  bestand,
}: {
  zeilen: readonly AbschnittZeile[];
  bestand: readonly AbschnittBestand[] | null;
}) {
  return (
    <>
      <table className="hidden w-full border-collapse md:table">
        <caption className="sr-only">
          Branchenabschnitte nach ÖNACE 2008 und ÖNACE 2025 mit Beschäftigungsverhältnissen am Stichtag
        </caption>
        <thead>
          <tr>
            <th scope="col" className={kopf}>
              Buchstabe
            </th>
            <th scope="col" className={kopf}>
              ÖNACE 2008, bis Dezember 2024
            </th>
            {bestand && (
              <th scope="col" className={`${kopf} text-right`}>
                Dez. 2024
              </th>
            )}
            <th scope="col" className={kopf}>
              ÖNACE 2025, ab Jänner 2025
            </th>
            {bestand && (
              <th scope="col" className={`${kopf} text-right`}>
                Jän. 2025
              </th>
            )}
            <th scope="col" className={`${kopf} pr-0`}>
              Vergleich
            </th>
          </tr>
        </thead>
        <tbody>
          {zeilen.map((z) => (
            <tr key={z.code} className="border-b border-line" data-abschnitt={z.code}>
              <th scope="row" className={`${zelle} text-left font-mono font-medium`}>
                {z.code}
              </th>
              <td className={zelle}>{z.alt?.bezeichnung ?? <span className="text-slate">gab es nicht</span>}</td>
              {bestand && (
                <td className={zahlZelle}>{z.alt ? <Wert wert={wertVon(bestand, "2008", z.code)} /> : null}</td>
              )}
              <td className={zelle}>{z.neu?.bezeichnung ?? <span className="text-slate">gibt es nicht mehr</span>}</td>
              {bestand && (
                <td className={zahlZelle}>{z.neu ? <Wert wert={wertVon(bestand, "2025", z.code)} /> : null}</td>
              )}
              <td className={`${zelle} pr-0`}>
                <Vergleich vergleich={z.vergleich} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul className="flex flex-col md:hidden" aria-label="Branchenabschnitte">
        {zeilen.map((z) => (
          <li key={z.code} className="flex flex-col gap-1 border-b border-line py-3" data-abschnitt={z.code}>
            <div className="flex items-baseline justify-between gap-4">
              <span className="font-mono text-16 font-semibold text-ink">{z.code}</span>
              <span className="font-sans text-14">
                <Vergleich vergleich={z.vergleich} />
              </span>
            </div>
            <p className="font-sans text-14 text-ink">
              {`2008: ${z.alt?.bezeichnung ?? "gab es nicht"}`}
              {bestand && z.alt && (
                <span className="block font-mono text-12 tabular-nums text-slate">
                  Dez. 2024: <Wert wert={wertVon(bestand, "2008", z.code)} />
                </span>
              )}
            </p>
            <p className="font-sans text-14 text-ink">
              {`2025: ${z.neu?.bezeichnung ?? "gibt es nicht mehr"}`}
              {bestand && z.neu && (
                <span className="block font-mono text-12 tabular-nums text-slate">
                  Jän. 2025: <Wert wert={wertVon(bestand, "2025", z.code)} />
                </span>
              )}
            </p>
          </li>
        ))}
      </ul>
    </>
  );
}
