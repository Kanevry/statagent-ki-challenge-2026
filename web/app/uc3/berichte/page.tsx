import type { Metadata } from "next";
import Link from "next/link";
import { Fliesstext, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { formatZahl, HerkunftChip } from "@kic/ui/bausteine";
import { leseBerichtsliste, sqlBerichtsliste, sqlBerichtsuebersicht, type Berichtszeile } from "@/lib/uc3/bericht";
import { leerSatz } from "@/lib/uc3/db";
import { Fachbegriff } from "@/lib/uc3/fachbegriff";
import { monatName } from "@/lib/uc3/monat";
import { berichtPfad } from "@/lib/uc3/navigation";
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

function monateText(n: number): string {
  return n === 1 ? "einem Monat" : `${formatZahl(n)} Monaten`;
}

export default async function Berichte() {
  const lesung = await leseBerichtsliste();

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

  return (
    <>
      <header className="flex max-w-4xl flex-col gap-4">
        <Ueberschrift stufe={2} als="h1" className="hyphens-auto break-words">
          {`Für jeden der ${formatZahl(zeilen.length)} gerechneten Monate liegt ein Qualitätsbericht vor; in ${
            nichtErklaerbar === 0
              ? "keinem davon"
              : nichtErklaerbar === zeilen.length
                ? `allen ${formatZahl(nichtErklaerbar)}`
                : monateText(nichtErklaerbar)
          } ist etwas nicht erklärbar.`}
        </Ueberschrift>
        <HerkunftChip quelle="meta.pruefung_treffer" sql={sqlBerichtsuebersicht()} />
        <Fliesstext>
          {`Jeder Bericht zeigt, was gelesen und gezählt wurde, was auffiel und wie es eingestuft ist. In ${
            mitRevision === 0 ? "keinem Monat" : monateText(mitRevision)
          } weicht eine schon gezeigte Zahl eines Vormonats ab; sie bleibt stehen und ist als Revisionsbedarf ausgewiesen.`}
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
        <HerkunftChip quelle="meta.pruefung_treffer" sql={sqlBerichtsliste()} />
        <Liste zeilen={zeilen} />
      </section>
    </>
  );
}

function Liste({ zeilen }: { zeilen: readonly Berichtszeile[] }) {
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
              Revisionsbedarf
            </th>
            <th scope="col" className={`${kopf} pr-0`}>
              Stand
            </th>
          </tr>
        </thead>
        <tbody>
          {zeilen.map(({ monat, revisionsbedarf }) => (
            <tr key={monat.lieferung} className="border-b border-line" data-lieferung={monat.lieferung}>
              <th scope="row" className={`${zelle} text-left font-medium`}>
                <Link href={berichtPfad(monat.lieferung)} className={link}>
                  {monatName(monat.lieferung)}
                </Link>
              </th>
              <td className={zahlZelle}>{formatZahl(monat.auffaelligkeiten)}</td>
              <td className={zahlZelle}>{formatZahl(monat.nichtErklaerbar)}</td>
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
        {zeilen.map(({ monat, revisionsbedarf }) => (
          <li key={monat.lieferung} className="flex flex-col gap-2 border-b border-line py-4" data-lieferung={monat.lieferung}>
            <div className="flex items-baseline justify-between gap-4">
              <Link href={berichtPfad(monat.lieferung)} className={`font-sans text-16 font-semibold ${link}`}>
                {monatName(monat.lieferung)}
              </Link>
              <MonatsStatus monat={monat} />
            </div>
            <p className="font-sans text-14 text-ink">
              <span className="font-mono tabular-nums">{formatZahl(monat.auffaelligkeiten)}</span>
              {" Auffälligkeiten, davon "}
              <span className="font-mono tabular-nums">{formatZahl(monat.nichtErklaerbar)}</span>
              {" nicht erklärbar · Revisionsbedarf "}
              <Revision ja={revisionsbedarf} />
            </p>
          </li>
        ))}
      </ul>
    </>
  );
}
