import { formatZahl } from "@kic/ui/bausteine";
import {
  abschnitteNachName,
  type AbschnittBestand,
  type AbschnittZeile,
  type NamensVergleich,
} from "@/components/uc3/klassifikation";

const kopf = "border-b border-ink py-2 pr-4 text-left align-bottom font-sans text-12 font-semibold text-slate";
const zelle = "py-2 pr-4 align-top font-sans text-14 text-ink";
const zahlZelle = `${zelle} text-right font-mono tabular-nums`;
const codeZelle = `${zelle} font-mono font-medium`;

/** Vergleich in einfachen Worten. */
const VERGLEICH: Record<NamensVergleich, string> = {
  gleich: "gleicher Buchstabe",
  gewechselt: "Buchstabe gewechselt",
  neu: "neu zugeschnitten",
  entfaellt: "gibt es 2025 nicht mehr",
};

function Vergleich({ vergleich }: { vergleich: NamensVergleich }) {
  const betont = vergleich !== "gleich";
  return <span className={betont ? "font-semibold text-warn-fg" : "text-ink"}>{VERGLEICH[vergleich]}</span>;
}

function wertVon(bestand: readonly AbschnittBestand[] | null, version: string, code: string | null): number | null {
  if (!bestand || !code) return null;
  return bestand.find((b) => b.version === version && b.code === code)?.wert ?? null;
}

function Wert({ wert }: { wert: number | null }) {
  return wert === null ? <span className="font-sans text-12 text-slate">keiner</span> : <>{formatZahl(wert)}</>;
}

/**
 * Eine Branche je Zeile, nach Namen geordnet, daneben ihr Buchstabe in ÖNACE 2008 und 2025. So sieht man, dass
 * dieselbe Branche ab Jänner 2025 oft unter einem anderen Buchstaben steht (Gesundheits- und Sozialwesen: 2008 Q,
 * 2025 R). Ab 768 px eine Tabelle, darunter eine Liste mit denselben Angaben.
 */
export function Abschnittstabelle({
  zeilen,
  bestand,
}: {
  zeilen: readonly AbschnittZeile[];
  bestand: readonly AbschnittBestand[] | null;
}) {
  const branchen = abschnitteNachName(zeilen);
  return (
    <>
      <table className="hidden w-full border-collapse md:table">
        <caption className="sr-only">
          Branchenabschnitte nach Namen, mit Buchstabe in ÖNACE 2008 und ÖNACE 2025 und Beschäftigungsverhältnissen am
          Stichtag
        </caption>
        <thead>
          <tr>
            <th scope="col" className={kopf}>
              Branche
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
          {branchen.map((z) => (
            <tr key={z.bezeichnung} className="border-b border-line" data-abschnitt={z.codeNeu ?? z.codeAlt ?? ""}>
              <th scope="row" className={`${zelle} text-left font-normal`}>
                {z.bezeichnung}
              </th>
              <td className={codeZelle}>{z.codeAlt ?? <span className="font-sans text-slate">gab es nicht</span>}</td>
              {bestand && <td className={zahlZelle}>{z.codeAlt ? <Wert wert={wertVon(bestand, "2008", z.codeAlt)} /> : null}</td>}
              <td className={codeZelle}>{z.codeNeu ?? <span className="font-sans text-slate">gibt es nicht mehr</span>}</td>
              {bestand && <td className={zahlZelle}>{z.codeNeu ? <Wert wert={wertVon(bestand, "2025", z.codeNeu)} /> : null}</td>}
              <td className={`${zelle} pr-0`}>
                <Vergleich vergleich={z.vergleich} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul className="flex flex-col md:hidden" aria-label="Branchenabschnitte">
        {branchen.map((z) => (
          <li key={z.bezeichnung} className="flex flex-col gap-1 border-b border-line py-3" data-abschnitt={z.codeNeu ?? z.codeAlt ?? ""}>
            <p className="break-words font-sans text-16 font-semibold text-ink">{z.bezeichnung}</p>
            <p className="font-sans text-14">
              <Vergleich vergleich={z.vergleich} />
            </p>
            <p className="font-sans text-14 text-ink">
              {`2008: ${z.codeAlt ?? "gab es nicht"}`}
              {bestand && z.codeAlt && (
                <span className="block font-mono text-12 tabular-nums text-slate">
                  Dez. 2024: <Wert wert={wertVon(bestand, "2008", z.codeAlt)} />
                </span>
              )}
            </p>
            <p className="font-sans text-14 text-ink">
              {`2025: ${z.codeNeu ?? "gibt es nicht mehr"}`}
              {bestand && z.codeNeu && (
                <span className="block font-mono text-12 tabular-nums text-slate">
                  Jän. 2025: <Wert wert={wertVon(bestand, "2025", z.codeNeu)} />
                </span>
              )}
            </p>
          </li>
        ))}
      </ul>
    </>
  );
}
