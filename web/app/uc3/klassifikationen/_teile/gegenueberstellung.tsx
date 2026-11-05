import { aenderungsSatz, type GegenueberZeile } from "@/components/uc3/klassifikation";

const kopf = "border-b border-ink py-2 align-bottom font-sans text-12 font-semibold text-slate";
const zelle = "border-b border-line py-3 align-top font-sans";

/** Buchstabe 2025: hervorgehoben, wenn er sich vom Buchstaben 2008 unterscheidet. */
function NeuBuchstaben({ zeile }: { zeile: GegenueberZeile }) {
  if (zeile.neu.length === 0) return <span className="sr-only">gibt es nicht mehr</span>;
  return (
    <span className="flex flex-col items-end gap-1">
      {zeile.neu.map((n) => {
        const anders = n.code !== zeile.alt?.code;
        return (
          <span key={n.code} className={anders ? "font-semibold text-ink" : "text-slate"}>
            {n.code}
            {anders && zeile.alt && <span className="sr-only">{`, vorher ${zeile.alt.code}`}</span>}
          </span>
        );
      })}
    </span>
  );
}

/**
 * ÖNACE 2008 links, ÖNACE 2025 rechts, je Branche eine Zeile nach Namen (UI-Regie v1). In der Mitte der Name, bei
 * Teilung oder neuem Namen ein Satz darunter. Drei schmale Spalten, damit die Tabelle auch bei 375 px passt.
 */
export function Gegenueberstellung({ zeilen }: { zeilen: readonly GegenueberZeile[] }) {
  return (
    <table className="w-full max-w-4xl border-collapse">
      <caption className="sr-only">
        Branchen nach Namen, links der Buchstabe in ÖNACE 2008 bis Dezember 2024, rechts der Buchstabe in ÖNACE 2025 ab
        Jänner 2025
      </caption>
      <thead>
        <tr>
          <th scope="col" className={`${kopf} w-20 pr-4 text-left sm:w-28`}>
            ÖNACE 2008
          </th>
          <th scope="col" className={`${kopf} pr-4 text-left`}>
            Branche
          </th>
          <th scope="col" className={`${kopf} w-20 text-right sm:w-28`}>
            ÖNACE 2025
          </th>
        </tr>
      </thead>
      <tbody>
        {zeilen.map((z) => {
          const satz = aenderungsSatz(z);
          return (
            <tr key={`${z.alt?.code ?? ""}-${z.name}`} data-abschnitt={z.alt?.code ?? z.neu[0]?.code ?? ""}>
              <td className={`${zelle} pr-4 text-16 text-slate`}>
                {z.alt ? z.alt.code : <span className="sr-only">gab es nicht</span>}
              </td>
              <th scope="row" className={`${zelle} pr-4 text-left font-normal`}>
                <span className="block break-words text-16 text-ink">{z.name}</span>
                {satz && <span className="mt-1 block max-w-2xl text-14 text-slate">{satz}</span>}
              </th>
              <td className={`${zelle} text-right text-16`}>
                <NeuBuchstaben zeile={z} />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
