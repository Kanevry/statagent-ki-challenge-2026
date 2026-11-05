import type { Metadata } from "next";
import Link from "next/link";
import { Fliesstext, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { formatZahl, HerkunftChip } from "@kic/ui/bausteine";
import {
  leseBerichtsliste,
  rueckfragenInAllenMonaten,
  sqlBerichtsliste,
  sqlBerichtsuebersicht,
  sqlOhneRueckfrage,
  type Berichtszeile,
} from "@/components/uc3/bericht";
import { aufzaehlen } from "@/components/uc3/lauf-detail";
import { leerSatz } from "@/components/uc3/db";
import { Fachbegriff } from "@/components/uc3/fachbegriff";
import { monatName } from "@/components/uc3/monat";
import { berichtPfad, regelsatzAus } from "@/components/uc3/navigation";
import { MonatsStatus } from "../_teile/monatstabelle";

// Qualitätsberichte (#18, Frame fJdk9): ein Bericht je Monat aus dem maßgeblichen Lauf. Ohne Datenbank der
// Leerzustand mit HTTP 200.
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Qualitätsberichte · StatAgent" };

const kopf = "border-b border-ink py-2 pr-4 text-left align-bottom font-sans text-12 font-semibold text-slate";
const zelle = "py-2 pr-4 align-top font-sans text-14 text-ink";
const zahlZelle = `${zelle} text-right font-mono tabular-nums`;
const link = "text-ink underline underline-offset-4 hover:text-gruen";

function Revision({ ja }: { ja: boolean }) {
  return <>{ja ? "ja" : "nein"}</>;
}

function wartetText(wartet: readonly string[]): string {
  return wartet.length ? `${aufzaehlen(wartet)} ${wartet.length === 1 ? "wartet" : "warten"} auf die Fachabteilung` : "nichts";
}

function monateText(n: number): string {
  return n === 1 ? "einem Monat" : `${formatZahl(n)} Monaten`;
}

type Props = { searchParams: Promise<{ regelsatz?: string | string[] }> };

export default async function Berichte({ searchParams }: Props) {
  const regelsatz = regelsatzAus((await searchParams).regelsatz);
  const lesung = await leseBerichtsliste(regelsatz);

  if (!lesung.ok || lesung.daten.length === 0) {
    return (
      <>
        <Ueberschrift stufe={2} als="h1">
          Qualitätsberichte
        </Ueberschrift>
        <Leerzustand
          satz={lesung.ok ? "Noch kein Monat ist gerechnet, deshalb gibt es noch keinen Qualitätsbericht." : leerSatz(lesung.grund)}
        />
      </>
    );
  }

  const zeilen = lesung.daten;
  const nichtErklaerbar = zeilen.filter((z) => z.monat.nichtErklaerbar > 0).length;
  const mitRevision = zeilen.filter((z) => z.revisionsbedarf).length;
  const ueberall = rueckfragenInAllenMonaten(zeilen);
  const weitere = zeilen.filter((z) => z.ohneRueckfrage > 0).length;
  const n = formatZahl(zeilen.length);
  const kopfsatz =
    ueberall.length > 0
      ? `Für alle ${n} Monate liegt ein Qualitätsbericht vor, in jedem Monat wartet die Rückfrage ${aufzaehlen(ueberall)} auf eine Antwort der Fachabteilung.`
      : nichtErklaerbar === 0
        ? `Für alle ${n} Monate liegt ein Qualitätsbericht vor, alle Auffälligkeiten sind erklärt.`
        : `Für alle ${n} Monate liegt ein Qualitätsbericht vor, in ${monateText(nichtErklaerbar)} wartet eine Auffälligkeit auf eine Erklärung.`;

  return (
    <>
      <header className="flex max-w-4xl flex-col gap-4">
        <Ueberschrift stufe={2} als="h1" className="hyphens-auto break-words">
          {kopfsatz}
        </Ueberschrift>
        <HerkunftChip quelle="meta.rueckfrage" sql={sqlBerichtsuebersicht(regelsatz)} />
        {ueberall.length > 0 && (
          <Fliesstext>
            {`Bis die Antwort da ist, bleibt diese Auffälligkeit in jedem Monat „nicht erklärbar“. Das ist so gewollt: Das Programm rät nicht, ein Mensch muss es klären.`}
          </Fliesstext>
        )}
        {weitere > 0 && (
          <div className="flex flex-col items-start gap-2">
            <Fliesstext>
              {`In ${monateText(weitere)} ist zusätzlich etwas nicht erklärbar, wozu noch keine Rückfrage gestellt ist. Der Bericht des Monats nennt es.`}
            </Fliesstext>
            <HerkunftChip quelle="meta.pruefung_treffer" sql={sqlOhneRueckfrage(regelsatz)} />
          </div>
        )}
        <Fliesstext>
          {`Jeder Bericht zeigt, was gelesen und gezählt wurde, was auffiel und wie es eingestuft ist. In ${
            mitRevision === 0 ? "keinem Monat" : monateText(mitRevision)
          } weicht eine schon gezeigte Zahl eines Vormonats ab. Sie bleibt stehen und ist als Revisionsbedarf ausgewiesen.`}
        </Fliesstext>
        <Fliesstext groesse={14}>
          <Link href="/uc3/berichte/regeln" className={link}>
            Alle Regeln lesen, nach denen gezählt wird
          </Link>
        </Fliesstext>
      </header>

      <ul className="grid max-w-5xl gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Begriffe auf dieser Seite">
        {(["Qualitätsbericht", "Auffälligkeit", "Revisionsbedarf", "Regel"] as const).map((wort) => (
          <li key={wort} className="font-sans text-14 font-semibold text-ink">
            <Fachbegriff wort={wort} />
          </li>
        ))}
      </ul>

      <section aria-labelledby="liste-titel" className="flex flex-col gap-4">
        <Ueberschrift stufe={3} als="h2" id="liste-titel">
          Jeder Monat hat seinen eigenen Bericht aus seinem maßgeblichen Lauf.
        </Ueberschrift>
        <HerkunftChip quelle="meta.pruefung_treffer" sql={sqlBerichtsliste(regelsatz)} />
        <Liste zeilen={zeilen} regelsatz={regelsatz} />
      </section>
    </>
  );
}

function Liste({ zeilen, regelsatz }: { zeilen: readonly Berichtszeile[]; regelsatz: string }) {
  return (
    <>
      <table className="hidden w-full max-w-5xl border-collapse md:table">
        <caption className="sr-only">Qualitätsberichte je Monat mit Auffälligkeiten, Revisionsbedarf und Stand</caption>
        <thead>
          <tr>
            <th scope="col" className={kopf}>
              Monat
            </th>
            <th scope="col" className={`${kopf} text-right`}>
              Auffälligkeiten
            </th>
            <th scope="col" className={`${kopf} text-right`}>
              davon nicht erklärbar
            </th>
            <th scope="col" className={kopf}>
              wartet auf Antwort
            </th>
            <th scope="col" className={kopf}>
              Revisionsbedarf
            </th>
            <th scope="col" className={`${kopf} pr-0`}>
              Stand
            </th>
          </tr>
        </thead>
        <tbody>
          {zeilen.map(({ monat, revisionsbedarf, wartet }) => (
            <tr key={monat.lieferung} className="border-b border-line" data-lieferung={monat.lieferung}>
              <th scope="row" className={`${zelle} text-left font-medium`}>
                <Link href={berichtPfad(monat.lieferung, regelsatz)} className={link}>
                  {monatName(monat.lieferung)}
                </Link>
              </th>
              <td className={zahlZelle}>{formatZahl(monat.auffaelligkeiten)}</td>
              <td className={zahlZelle}>{formatZahl(monat.nichtErklaerbar)}</td>
              <td className={zelle}>{wartetText(wartet)}</td>
              <td className={zelle}>
                <Revision ja={revisionsbedarf} />
              </td>
              <td className={`${zelle} pr-0`}>
                <MonatsStatus monat={monat} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul className="flex flex-col md:hidden" aria-label="Monate">
        {zeilen.map(({ monat, revisionsbedarf, wartet }) => (
          <li key={monat.lieferung} className="flex flex-col gap-2 border-b border-line py-4" data-lieferung={monat.lieferung}>
            <div className="flex items-baseline justify-between gap-4">
              <Link href={berichtPfad(monat.lieferung, regelsatz)} className={`font-sans text-16 font-semibold ${link}`}>
                {monatName(monat.lieferung)}
              </Link>
              <MonatsStatus monat={monat} />
            </div>
            <p className="font-sans text-14 text-ink">
              <span className="font-mono tabular-nums">{formatZahl(monat.auffaelligkeiten)}</span>
              {" Auffälligkeiten, davon "}
              <span className="font-mono tabular-nums">{formatZahl(monat.nichtErklaerbar)}</span>
              {` nicht erklärbar${wartet.length ? `, ${wartetText(wartet)}` : ""} · Revisionsbedarf `}
              <Revision ja={revisionsbedarf} />
            </p>
          </li>
        ))}
      </ul>
    </>
  );
}
