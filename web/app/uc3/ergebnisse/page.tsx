import type { Metadata } from "next";
import Link from "next/link";
import { Fliesstext, Ueberschrift } from "@kic/ui/basis";
import { EXCEL_DATEIEN, excelGroesseKb, excelPfad } from "@/components/uc3/ergebnisse";
import { MinisteriumListe } from "@/components/uc3/ministerium-liste";

// Feste Stelle für die Abgabe-Ergebnisse. Liest Dateien erst zur Laufzeit: Beim Bauen des Images fehlt abgabe/ noch.
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Ergebnisse · StatAgent" };

const titel = "font-sans text-16 font-semibold text-ink";
const link = "text-ink underline underline-offset-4 hover:text-gruen";

export default async function Ergebnisse() {
  const dateien = await Promise.all(EXCEL_DATEIEN.map(async (d) => ({ ...d, kb: await excelGroesseKb(d.datei) })));
  return (
    <>
      <Ueberschrift stufe={2} als="h1">
        Die Ergebnisse der Abgabe
      </Ueberschrift>

      <section aria-labelledby="excel-titel" className="flex max-w-3xl flex-col gap-3">
        <h2 id="excel-titel" className={titel}>
          Die beiden Excel-Dateien
        </h2>
        <ul className="flex flex-col">
          {dateien.map((d) => (
            <li key={d.fassung} className="flex flex-col border-b border-line py-3">
              {d.kb === null ? (
                <span className="font-sans text-16 text-ink">{`${d.titel}: Die Datei fehlt in dieser Installation.`}</span>
              ) : (
                <a href={excelPfad(d.fassung)} download={d.datei} className="inline-flex min-h-11 items-center font-sans text-16 font-medium text-gruen underline underline-offset-4">
                  {d.titel}
                </a>
              )}
              <span className="font-sans text-14 text-slate">{d.kb === null ? d.inhalt : `${d.inhalt} ${d.datei}, ${d.kb} KB.`}</span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="berichte-titel" className="flex max-w-3xl flex-col gap-3">
        <h2 id="berichte-titel" className={titel}>
          Die Berichte je Monat
        </h2>
        <Fliesstext>
          {"Jeder Monat hat seinen Bericht als eigene Seite unter "}
          <Link href="/uc3/berichte" className={link}>
            Qualitätsberichte
          </Link>
          {". Eine PDF-Datei gibt es nicht."}
        </Fliesstext>
      </section>

      <section aria-labelledby="ministerium-titel" className="flex max-w-3xl flex-col gap-3">
        <h2 id="ministerium-titel" className={titel}>
          Die Liste für das Ministerium
        </h2>
        <MinisteriumListe />
      </section>
    </>
  );
}
