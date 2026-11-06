import type { Metadata } from "next";
import Link from "next/link";
import { Fliesstext, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { formatZahl, HerkunftChip } from "@kic/ui/bausteine";
import {
  leseBerichtsliste,
  rueckfragenInAllenMonaten,
  sqlBerichtsliste,
  sqlBerichtsstand,
  sqlBerichtsuebersicht,
  sqlOhneRueckfrage,
  type Berichtszeile,
  type OffeneRueckfrage,
} from "@/components/uc3/bericht";
import { aufzaehlen, pruefungTitel } from "@/components/uc3/lauf-detail";
import { DatenFehler } from "@/components/uc3/daten-fehler";
import { alltag } from "@/components/uc3/sprache";
import { Begriffsliste } from "@/components/uc3/fachbegriff";
import { monatName } from "@/components/uc3/monat";
import { berichtPfad, regelsatzAus } from "@/components/uc3/navigation";
import { standSumme } from "@/components/uc3/monatsstand";
import { MonatsStatus } from "../_teile/monatstabelle";
import { PruefungMalMonatTabelle } from "./_teile/pruefung-mal-monat";

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

/**
 * Kopf der Übersicht aus den Daten, ohne Nummern: Monate, deren Veröffentlichung an einer eigenen Rückfrage hängt,
 * namentlich; Rückfragen, die jeden Monat betreffen, mit ihrem Titel. Etwa: „März 2025 und Oktober 2025 warten auf die
 * Fachabteilung. In jedem Monat offen: Kurze Zweitmeldungen derselben Person.“ Die Nummern stehen in der Monatsliste.
 */
function kopfSaetze(zeilen: readonly Berichtszeile[], ueberall: readonly OffeneRueckfrage[]): string[] {
  const allgemein = new Set(ueberall.map((q) => q.nr));
  const halten = zeilen.filter((z) => z.haeltAn.some((nr) => !allgemein.has(nr)));
  const saetze: string[] = [];
  if (halten.length > 0) {
    saetze.push(
      `${aufzaehlen(halten.map((z) => monatName(z.monat.lieferung)))} ${halten.length === 1 ? "wartet" : "warten"} auf die Fachabteilung.`,
    );
  }
  for (const q of ueberall) saetze.push(`In jedem Monat offen: ${alltag(q.titel).replace(/\.$/, "")}.`);
  return saetze;
}

type Props = { searchParams: Promise<{ regelsatz?: string | string[] }> };

export default async function Berichte({ searchParams }: Props) {
  const regelsatz = regelsatzAus((await searchParams).regelsatz);
  const lesung = await leseBerichtsliste(regelsatz);

  if (!lesung.ok) return <DatenFehler grund={lesung.grund} />;
  if (lesung.daten.zeilen.length === 0) {
    return (
      <>
        <Ueberschrift stufe={2} als="h1">
          Qualitätsberichte
        </Ueberschrift>
        <Leerzustand
          satz="Noch kein Monat ist gerechnet, deshalb gibt es noch keinen Qualitätsbericht."
          aktion={
            <Link href="/uc3/ergebnisse" className={link}>
              Excel-Dateien der Abgabe herunterladen
            </Link>
          }
        />
      </>
    );
  }

  const { zeilen, offeneRueckfragen, pruefungen } = lesung.daten;
  const mitRevision = zeilen.filter((z) => z.revisionsbedarf).length;
  const ueberall = rueckfragenInAllenMonaten(zeilen, offeneRueckfragen);
  const saetze = kopfSaetze(zeilen, ueberall);
  const weitere = zeilen.filter((z) => z.ohneRueckfrage.length > 0).length;
  // Je Prüfung die Monate, in denen sie nicht erklärbar ist und keine Rückfrage hat.
  const ohneJePruefung = [...new Set(zeilen.flatMap((z) => z.ohneRueckfrage))].map((name) => ({
    name,
    monate: zeilen.filter((z) => z.ohneRueckfrage.includes(name)).map((z) => z.monat.lieferung),
  }));
  const kopfsatz = `Für alle ${formatZahl(zeilen.length)} Monate liegt ein Qualitätsbericht vor. ${standSumme(zeilen.map((z) => z.monat))}.`;

  return (
    <>
      <header className="flex max-w-4xl flex-col gap-4">
        <Ueberschrift stufe={2} als="h1" className="break-words">
          {kopfsatz}
        </Ueberschrift>
        <HerkunftChip quelle="meta.lauf" sql={sqlBerichtsstand(regelsatz)} />
        {saetze.length > 0 && (
          <div className="flex flex-col items-start gap-2">
            <Fliesstext>
              {`${saetze.join(" ")} Was an einer offenen Rückfrage hängt, bleibt „nicht erklärbar“, bis die Antwort da ist. Das ist so gewollt: Das Programm rät nicht, ein Mensch muss es klären.`}
            </Fliesstext>
            <HerkunftChip quelle="meta.rueckfrage" sql={sqlBerichtsuebersicht(regelsatz)} />
          </div>
        )}
        {weitere > 0 && (
          <div className="flex flex-col items-start gap-2">
            <Fliesstext>
              {`In ${monateText(weitere)} ist eine Auffälligkeit nicht erklärbar, zu der noch keine Rückfrage gestellt ist. ${ohneJePruefung
                .map(
                  (p) =>
                    `${p.monate.length === 1 ? `Im ${monatName(p.monate[0])}` : `In ${monateText(p.monate.length)}`}: ${pruefungTitel(p.name)} (Prüfung ${p.name.split("_")[0]}).`,
                )
                .join(" ")} Der Bericht des Monats nennt die Zahlen.`}
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
        <Fliesstext groesse={14}>
          <Link href="/uc3/ergebnisse" className={link}>
            Excel-Dateien der Abgabe herunterladen
          </Link>
        </Fliesstext>
      </header>

      <PruefungMalMonatTabelle daten={pruefungen} monate={zeilen.map((z) => z.monat.lieferung)} regelsatz={regelsatz} />

      <section aria-labelledby="liste-titel" className="flex flex-col gap-4">
        <Ueberschrift stufe={3} als="h2" id="liste-titel">
          Die Berichte je Monat
        </Ueberschrift>
        <HerkunftChip quelle="meta.pruefung_treffer" sql={sqlBerichtsliste(regelsatz)} />
        <Liste zeilen={zeilen} regelsatz={regelsatz} />
      </section>

      <Begriffsliste worte={["Qualitätsbericht", "Auffälligkeit", "Revisionsbedarf", "Regel"] as const} label="Begriffe auf dieser Seite" className="grid max-w-5xl gap-4 sm:grid-cols-2 lg:grid-cols-4" />
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
