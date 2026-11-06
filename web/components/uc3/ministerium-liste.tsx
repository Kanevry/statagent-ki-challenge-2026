import { formatZahl } from "@kic/ui/bausteine";
import { leseMinisteriumBeleg } from "./ergebnisse";
import { aufzaehlen } from "./lauf-detail";

// Die Liste für das Ministerium: kein Download, sie enthält Einzeldaten. Alle Angaben kommen aus dem Beleg im Repo.
export async function MinisteriumListe() {
  const beleg = await leseMinisteriumBeleg();
  if (!beleg) return <p className="font-sans text-16 text-ink">Der Beleg zur Liste fehlt in dieser Installation.</p>;
  return (
    <>
      <p className="font-sans text-16 text-pretty text-ink">
        {`Die Datei ${beleg.datei} mit ${formatZahl(beleg.personen)} Personen und den Spalten ${aufzaehlen(beleg.spalten)} enthält Einzeldaten, deshalb liegt sie nicht hier, sondern im `}
        <span className="whitespace-nowrap">SV-Box-Teamordner</span>.
      </p>
      <p className="font-sans text-14 text-slate">
        {"sha256 "}
        <span className="break-all font-mono text-12 text-ink">{beleg.sha256}</span>
      </p>
      <details>
        <summary className="inline-flex min-h-11 cursor-pointer items-center font-sans text-14 text-slate underline decoration-line underline-offset-4 hover:text-ink">
          Beleg ansehen
        </summary>
        <dl className="flex max-h-80 flex-col gap-2 overflow-auto border border-line bg-white p-3" tabIndex={0}>
          {beleg.zeilen.map((z) => (
            <div key={z.angabe}>
              <dt className="font-sans text-12 text-slate">{z.angabe}</dt>
              <dd className="break-words font-mono text-12 text-ink">{z.wert}</dd>
            </div>
          ))}
        </dl>
      </details>
    </>
  );
}
