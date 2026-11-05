import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { Fliesstext, Leerzustand, Status, Ueberschrift } from "@kic/ui/basis";
import { formatDifferenz, formatProzent, formatZahl, formatZeit, HerkunftChip } from "@kic/ui/bausteine";
import {
  annahmeSatz,
  leseQualitaetsbericht,
  sqlAnnahmen,
  sqlAnnahmeWirkung,
  sqlAuffaelligkeiten,
  sqlRevision,
  sqlRueckfragen,
  sqlUeberblick,
  type Auffaelligkeit,
  type Qualitaetsbericht,
} from "@/components/uc3/bericht";
import { bestandBeleg, laufBeleg } from "@/components/uc3/beleg";
import { leerSatz } from "@/components/uc3/db";
import { Fachbegriff } from "@/components/uc3/fachbegriff";
import { abrechnung } from "@/components/uc3/laeufe";
import { aufzaehlen, wartetSatz } from "@/components/uc3/lauf-detail";
import { istMonat, monatName, stichtag } from "@/components/uc3/monat";
import { berichtPfad, berichtslistePfad, laufPfad, regelsatzAus } from "@/components/uc3/navigation";
import { MonatsStatus } from "../../_teile/monatstabelle";

// Qualitätsbericht eines Monats (#18, Frame fJdk9) in den fünf Abschnitten des Generators
// (statagent.berichte.qualitaetsbericht): Überblick, Auffälligkeiten, Rückfragen, angewendete Regeln mit
// Annahmen, Revisionsbedarf. Jede Zahl trägt einen Beleg, dessen Abfrage sie liefert.
export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ lieferung: string }>;
  searchParams: Promise<{ regelsatz?: string | string[] }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { lieferung } = await params;
  return { title: `${istMonat(lieferung) ? `Qualitätsbericht ${monatName(lieferung)}` : "Qualitätsbericht"} · StatAgent` };
}

const kopf = "border-b border-ink py-2 pr-4 text-left align-bottom font-sans text-12 font-semibold text-slate";
const zelle = "py-2 pr-4 align-top font-sans text-14 text-ink";
const zahlZelle = `${zelle} text-right font-mono tabular-nums`;
const link = "text-ink underline underline-offset-4 hover:text-gruen";
const regelName = "font-mono text-12 text-slate break-all";

function mehrzahl(n: number, eins: string, viele: string): string {
  return `${formatZahl(n)} ${n === 1 ? eins : viele}`;
}

export default async function Bericht({ params, searchParams }: Props) {
  const { lieferung } = await params;
  if (!istMonat(lieferung)) notFound();
  const regelsatz = regelsatzAus((await searchParams).regelsatz);
  const lesung = await leseQualitaetsbericht(lieferung, regelsatz);
  const titel = `Qualitätsbericht ${monatName(lieferung)}${regelsatz === "v2" ? ", Regelsatz v2" : ""}`;

  if (!lesung.ok || lesung.daten === null) {
    return (
      <>
        <Ueberschrift stufe={2} als="h1">
          {titel}
        </Ueberschrift>
        <Leerzustand
          satz={
            lesung.ok
              ? regelsatz === "v2"
                ? `Für ${monatName(lieferung)} gibt es mit Regelsatz v2 noch keinen Lauf, deshalb auch keinen Qualitätsbericht.`
                : `Für ${monatName(lieferung)} gibt es noch keinen gerechneten Lauf, deshalb auch keinen Qualitätsbericht.`
              : leerSatz(lesung.grund)
          }
          aktion={
            <Link href={berichtslistePfad(regelsatz)} className={link}>
              Zu allen Qualitätsberichten
            </Link>
          }
        />
      </>
    );
  }

  const b = lesung.daten;
  const { lauf, auffaelligkeiten } = b;
  const nichtErklaerbar = auffaelligkeiten.filter((a) => a.einstufung.code === "nicht-erklaerbar").length;
  const anhaltend = auffaelligkeiten.filter((a) => a.anhalten);
  const monat = {
    ...lauf,
    laeufeGesamt: 0,
    angehalten: anhaltend.length > 0,
    anhaltendeRegeln: anhaltend.map((a) => a.regel),
    auffaelligkeiten: auffaelligkeiten.length,
    nichtErklaerbar,
  };

  return (
    <>
      <header className="flex max-w-4xl flex-col gap-4">
        <Fliesstext groesse={14} ton="gedaempft">
          {titel}
        </Fliesstext>
        <Ueberschrift stufe={2} als="h1" className="hyphens-auto break-words">
          {hauptsatz(lieferung, auffaelligkeiten)}
        </Ueberschrift>
        <HerkunftChip {...laufBeleg(lauf, { quelle: "meta.pruefung_treffer", sql: sqlAuffaelligkeiten(lauf) })} />
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <MonatsStatus monat={monat} />
          <Fliesstext groesse={14} ton="gedaempft">
            {`Gerechnet am ${formatZeit(lauf.gestartetAm)} mit Regelstand ${lauf.regelstand}. ${
              lauf.freigegebenVon ? `Freigegeben von ${lauf.freigegebenVon}.` : "Noch ohne Freigabe mit Namen."
            }`}
          </Fliesstext>
        </div>
        {anhaltend.length > 0 && (
          <Fliesstext>
            {`Der Monat ist angehalten, weil ${mehrzahl(anhaltend.length, "Prüfung", "Prüfungen")} angeschlagen ${
              anhaltend.length === 1 ? "hat" : "haben"
            }. Er braucht Ihr Urteil, bevor er veröffentlicht wird.`}
          </Fliesstext>
        )}
        <Fliesstext groesse={14}>
          <Link href={laufPfad(lieferung, regelsatz)} className={link}>
            {`Lauf ${monatName(lieferung)} im Detail ansehen`}
          </Link>
          {b.vormonat && (
            <>
              {" · "}
              <Link href={berichtPfad(b.vormonat.lieferung, regelsatz)} className={link}>
                {`Bericht ${monatName(b.vormonat.lieferung)}`}
              </Link>
            </>
          )}
        </Fliesstext>
      </header>

      <ul className="grid max-w-5xl gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Begriffe auf dieser Seite">
        {(["Qualitätsbericht", "Regelstand", "Auffälligkeit", "Einstufung", "Rückfrage", "Annahme", "Revisionsbedarf", "Sätze"] as const).map(
          (wort) => (
            <li key={wort} className="font-sans text-14 font-semibold text-ink">
              <Fachbegriff wort={wort} />
            </li>
          ),
        )}
      </ul>

      <UeberblickAbschnitt b={b} />
      <AuffaelligkeitenAbschnitt b={b} />
      <RueckfragenAbschnitt b={b} />
      <AnnahmenAbschnitt b={b} />
      <RevisionAbschnitt b={b} />
    </>
  );
}

function hauptsatz(lieferung: string, liste: readonly Auffaelligkeit[]): string {
  const m = monatName(lieferung);
  const alle = liste.length;
  const nicht = liste.filter((a) => a.einstufung.code === "nicht-erklaerbar");
  const nrn = [...new Set(nicht.flatMap((a) => a.offeneRueckfragen))].sort();
  const ohne = nicht.filter((a) => a.offeneRueckfragen.length === 0).length;
  const wartend = nicht.length - ohne;
  if (alle === 0) return `Im ${m} hat keine Prüfung etwas gefunden.`;
  const kopf = `Im ${m} ${alle === 1 ? "gab es eine Auffälligkeit" : `gab es ${formatZahl(alle)} Auffälligkeiten`}`;
  if (nicht.length === 0) return `${kopf}, ${alle === 1 ? "sie ist" : "alle sind"} erklärt.`;
  const erklaert = alle - nicht.length;
  const teile = [
    ...(wartend > 0
      ? [`${wartend === 1 ? "eine wartet" : `${formatZahl(wartend)} warten`} auf die Antwort der Fachabteilung (${aufzaehlen(nrn)})`]
      : []),
    ...(ohne > 0 ? [`${ohne === 1 ? "eine ist" : `${formatZahl(ohne)} sind`} noch nicht erklärbar`] : []),
  ];
  return `${kopf}. ${erklaert > 0 ? `${formatZahl(erklaert)} ${erklaert === 1 ? "ist" : "sind"} erklärt, ` : ""}${aufzaehlen(teile)}.`.replace(
    /\. ([a-zäöü])/,
    (_, c: string) => `. ${c.toUpperCase()}`,
  );
}

function Abschnitt({ nr, name, titel, children }: { nr: number; name: string; titel: string; children: ReactNode }) {
  const id = `abschnitt-${nr}`;
  return (
    <section aria-labelledby={id} className="flex max-w-5xl flex-col gap-4 border-t border-line pt-8">
      <Fliesstext groesse={14} ton="gedaempft">{`${nr} · ${name}`}</Fliesstext>
      <Ueberschrift stufe={3} als="h2" id={id} className="hyphens-auto break-words">
        {titel}
      </Ueberschrift>
      {children}
    </section>
  );
}

function UeberblickAbschnitt({ b }: { b: Qualitaetsbericht }) {
  const { lauf, ueberblick: u, vormonat } = b;
  const { ausLieferung, gehtAuf } = abrechnung(lauf);
  const zeilen: [string, number][] = [
    ["gelesene Sätze", u.gelesen],
    [`gezählt am Stichtag ${stichtag(lauf.lieferung)}`, u.gezaehlt],
    ...(u.fortgeschrieben > 0
      ? ([
          ["davon aus dieser Lieferung", ausLieferung],
          ["davon aus dem Vormonat übernommen (vorläufig)", u.fortgeschrieben],
        ] as [string, number][])
      : []),
    ["nicht gezählt (am Stichtag nicht beschäftigt)", u.nichtGezaehlt],
    ["ausgeschlossen", u.ausgeschlossen],
    ["korrigiert, aber gezählt", u.korrigiert],
  ];
  const differenz = vormonat ? lauf.gezaehlt - vormonat.gezaehlt : null;
  return (
    <Abschnitt
      nr={1}
      name="Überblick"
      titel={`Aus ${formatZahl(u.gelesen)} gelesenen Sätzen ergeben sich ${formatZahl(u.gezaehlt)} Beschäftigungsverhältnisse am Stichtag.`}
    >
      <HerkunftChip {...laufBeleg(lauf, { quelle: "meta.lauf", sql: sqlUeberblick(lauf) })} />
      <dl className="flex max-w-xl flex-col">
        {zeilen.map(([name, wert]) => (
          <div key={name} className="flex items-baseline justify-between gap-4 border-b border-line py-2">
            <dt className="font-sans text-14 text-ink">{name}</dt>
            <dd className="font-mono text-14 tabular-nums text-ink">{formatZahl(wert)}</dd>
          </div>
        ))}
      </dl>
      <Status art={gehtAuf ? "ok" : "fehler"}>
        {gehtAuf
          ? "Die Abrechnung geht auf: jeder gelesene Satz ist gezählt, nicht gezählt oder ausgeschlossen."
          : "Die Abrechnung geht nicht auf: gelesen ist nicht gleich gezählt, nicht gezählt und ausgeschlossen."}
      </Status>
      {vormonat && differenz !== null ? (
        <div className="flex flex-col items-start gap-2">
          <Fliesstext>
            {`Zum Vormonat ${monatName(vormonat.lieferung)} mit ${formatZahl(vormonat.gezaehlt)} Verhältnissen: `}
            <span className="font-mono tabular-nums">{formatDifferenz(differenz)}</span>
            {vormonat.gezaehlt > 0 && (
              <span className="font-mono tabular-nums">{` (${formatProzent((differenz / vormonat.gezaehlt) * 100)})`}</span>
            )}
            .
          </Fliesstext>
          <HerkunftChip {...bestandBeleg(vormonat)} />
        </div>
      ) : (
        <Fliesstext groesse={14} ton="gedaempft">
          Für den Vormonat gibt es keinen Lauf, deshalb fehlt der Vergleich.
        </Fliesstext>
      )}
    </Abschnitt>
  );
}

function Einstufung({ a }: { a: Auffaelligkeit }) {
  const wartet = a.einstufung.code === "nicht-erklaerbar" ? wartetSatz(a.offeneRueckfragen) : null;
  return <Status art={wartet ? "warnung" : a.einstufung.art}>{wartet ? `${a.einstufung.wort}, ${wartet}` : a.einstufung.wort}</Status>;
}

function Pruefabfrage({ a }: { a: Auffaelligkeit }) {
  if (!a.belegSql) return null;
  return (
    <details className="font-sans text-12 text-slate">
      <summary className="cursor-pointer underline underline-offset-4">Abfrage der Prüfung</summary>
      <pre className="mt-2 max-w-full overflow-x-auto border border-line bg-paper p-2 font-mono text-12 text-ink">
        {a.belegSql}
      </pre>
    </details>
  );
}

function AuffaelligkeitenAbschnitt({ b }: { b: Qualitaetsbericht }) {
  const liste = b.auffaelligkeiten;
  const titel =
    liste.length === 0
      ? b.pruefungenGelaufen === 0
        ? "Für diesen Lauf liegen keine Prüfergebnisse vor."
        : `Keine von ${formatZahl(b.pruefungenGelaufen)} Prüfungen hat in diesem Monat etwas gefunden.`
      : `${mehrzahl(liste.length, "Prüfung hat", "Prüfungen haben")} etwas gefunden, jede Auffälligkeit ist eingestuft.`;
  return (
    <Abschnitt nr={2} name="Auffälligkeiten" titel={titel}>
      <HerkunftChip {...laufBeleg(b.lauf, { quelle: "meta.pruefung_treffer", sql: sqlAuffaelligkeiten(b.lauf) })} />
      {liste.length > 0 && (
        <>
          <Fliesstext groesse={14} ton="gedaempft">
            Erklärt, plausibel: eine echte Entwicklung. Erklärt, Datenproblem: die Ursache liegt in den Daten, die
            Maßnahme ist umgesetzt. Nicht erklärbar: Das Programm rät nicht, die Fachabteilung bekommt eine Rückfrage.
          </Fliesstext>
          <table className="hidden w-full border-collapse md:table">
            <caption className="sr-only">Auffälligkeiten mit Umfang, Einstufung, Maßnahme und Rückfrage</caption>
            <thead>
              <tr>
                <th scope="col" className={`${kopf} text-right`}>
                  Nr.
                </th>
                <th scope="col" className={kopf}>
                  Was auffiel
                </th>
                <th scope="col" className={kopf}>
                  Umfang
                </th>
                <th scope="col" className={kopf}>
                  Einstufung
                </th>
                <th scope="col" className={kopf}>
                  Maßnahme
                </th>
                <th scope="col" className={`${kopf} pr-0`}>
                  Rückfrage
                </th>
              </tr>
            </thead>
            <tbody>
              {liste.map((a) => (
                <tr key={`${a.regel}-${a.nr}`} className="border-b border-line">
                  <td className={zahlZelle}>{a.nr}</td>
                  <td className={`${zelle} max-w-md`}>
                    <span className="block">{a.satz}</span>
                    <span className={regelName}>{`${a.regel} · Ebene ${a.ebene}`}</span>
                    <Pruefabfrage a={a} />
                  </td>
                  <td className={`${zelle} font-mono tabular-nums`}>{a.umfang}</td>
                  <td className={zelle}>
                    <Einstufung a={a} />
                    {a.anhalten && <span className="mt-1 block font-sans text-12 text-slate">hält den Monat an</span>}
                  </td>
                  <td className={zelle} title={a.massnahmeRoh ?? undefined}>
                    {a.massnahme}
                  </td>
                  <td className={`${zelle} pr-0 font-mono`}>{a.rueckfragen.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <ol className="flex flex-col md:hidden" aria-label="Auffälligkeiten">
            {liste.map((a) => (
              <li key={`${a.regel}-${a.nr}`} className="flex flex-col gap-2 border-b border-line py-4">
                <Einstufung a={a} />
                <p className="font-sans text-14 text-ink">{`${a.nr}. ${a.satz}`}</p>
                <p className="font-sans text-12 text-slate">
                  {`Umfang: ${a.umfang}${a.anhalten ? " · hält den Monat an" : ""}${
                    a.rueckfragen.length ? ` · Rückfrage ${a.rueckfragen.join(", ")}` : ""
                  }`}
                </p>
                <p className="font-sans text-14 text-ink">{`Maßnahme: ${a.massnahme}`}</p>
                <span className={regelName}>{a.regel}</span>
                <Pruefabfrage a={a} />
              </li>
            ))}
          </ol>
        </>
      )}
    </Abschnitt>
  );
}

function RueckfragenAbschnitt({ b }: { b: Qualitaetsbericht }) {
  const liste = b.rueckfragen;
  const offen = liste.filter((r) => r.offen).length;
  const titel =
    liste.length === 0
      ? "Für diesen Monat gibt es keine Rückfrage an die Fachabteilung."
      : `${mehrzahl(liste.length, "Rückfrage", "Rückfragen")} an die Fachabteilung ${liste.length === 1 ? "betrifft" : "betreffen"} diesen Monat, ${
          offen === 0
            ? "alle sind beantwortet"
            : offen === liste.length
              ? `${liste.length === 1 ? "sie ist" : "alle sind"} noch offen`
              : `${formatZahl(offen)} davon ${offen === 1 ? "ist" : "sind"} noch offen`
        }.`;
  return (
    <Abschnitt nr={3} name="Rückfragen an die Fachabteilung" titel={titel}>
      <HerkunftChip {...laufBeleg(b.lauf, { quelle: "meta.rueckfrage", sql: sqlRueckfragen(b.lauf) })} />
      {liste.length > 0 && (
        <ul className="flex flex-col">
          {liste.map((r) => (
            <li key={r.nr} className="flex flex-col gap-1 border-b border-line py-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="font-sans text-16 font-semibold text-ink">
                  <span className="mr-2 font-mono text-14 text-slate">{r.nr}</span>
                  {r.titel}
                </p>
                <Status art={r.offen ? "warnung" : "ok"}>{r.offen ? "offen" : "beantwortet"}</Status>
              </div>
              <Fliesstext>{r.frage}</Fliesstext>
              <Fliesstext groesse={14} ton="gedaempft">
                {r.offen
                  ? `Bis zur Antwort gilt: ${r.vorschlag}`
                  : `Antwort${r.antwortAm ? ` vom ${r.antwortAm}` : ""}: ${r.antwort ?? ""}`}
              </Fliesstext>
              {r.regelName && <span className={regelName}>{r.regelName}</span>}
            </li>
          ))}
        </ul>
      )}
    </Abschnitt>
  );
}

function AnnahmenAbschnitt({ b }: { b: Qualitaetsbericht }) {
  const { lauf, annahmen } = b;
  const gesamt = new Set([lauf.gezaehlt, lauf.gelesen + lauf.fortgeschrieben]);
  const titel =
    annahmen.length === 0
      ? "In diesem Monat gilt keine Annahme."
      : `In diesem Monat ${annahmen.length === 1 ? "gilt eine Annahme" : `gelten ${formatZahl(annahmen.length)} Annahmen`}, jede umgesetzt als Regel.`;
  return (
    <Abschnitt nr={4} name="Angewendete Regeln: Annahmen in diesem Monat" titel={titel}>
      <HerkunftChip {...laufBeleg(lauf, { quelle: b.annahmenQuelle, sql: sqlAnnahmen(lauf, b.annahmenQuelle) })} />
      {annahmen.length > 0 && (
        <ul className="flex flex-col">
          {annahmen.map((a) => (
            <li key={a.nr} className="flex flex-col gap-2 border-b border-line py-4">
              <Fliesstext className="font-medium">{annahmeSatz(a.satz)}</Fliesstext>
              <Fliesstext groesse={14}>
                {a.wirkungSaetze === null || a.wirkungSaetze === 0 ? (
                  "In diesem Monat hat die Regel keinen Satz verändert."
                ) : (
                  <>
                    {"Betrifft in diesem Monat "}
                    <span className="font-mono tabular-nums">{formatZahl(a.wirkungSaetze)}</span>
                    {" Sätze."}
                    {gesamt.has(a.wirkungSaetze) && " Das ist die Gesamtzahl, die die Regel durchläuft, nicht nur veränderte Sätze."}
                  </>
                )}
              </Fliesstext>
              {a.begruendung && (
                <Fliesstext groesse={14} ton="gedaempft">{`Begründung: ${a.begruendung}`}</Fliesstext>
              )}
              <span className={regelName}>
                {[a.nr !== a.regelName ? a.nr : null, a.regelName, a.rueckfrage ? `Rückfrage ${a.rueckfrage}` : null]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
              {a.regelName && (
                <HerkunftChip
                  {...laufBeleg(lauf, { quelle: "meta.regel_wirkung", sql: sqlAnnahmeWirkung(lauf, a.regelName), stand: null })}
                />
              )}
            </li>
          ))}
        </ul>
      )}
    </Abschnitt>
  );
}

function RevisionAbschnitt({ b }: { b: Qualitaetsbericht }) {
  const { revision: zeilen, revisionGeprueft } = b;
  const titel =
    zeilen.length > 0
      ? `Für ${mehrzahl(zeilen.length, "früheren Monat", "frühere Monate")} zeigt diese Lieferung andere Zahlen, die schon gezeigten Zahlen bleiben stehen.`
      : revisionGeprueft > 0
        ? `Kein Revisionsbedarf: ${mehrzahl(revisionGeprueft, "geprüfter Vormonat stimmt", "geprüfte Vormonate stimmen")} mit dieser Lieferung überein.`
        : "Für diesen Monat gibt es keinen Abgleich mit früheren Monaten.";
  return (
    <Abschnitt nr={5} name="Revisionsbedarf früherer Monate" titel={titel}>
      <HerkunftChip {...laufBeleg(b.lauf, { quelle: "meta.revision", sql: sqlRevision(b.lauf) })} />
      {zeilen.length > 0 && (
        <>
          <table className="hidden w-full border-collapse md:table">
            <caption className="sr-only">Revisionsbedarf je früherem Monat</caption>
            <thead>
              <tr>
                <th scope="col" className={kopf}>
                  Monat
                </th>
                <th scope="col" className={`${kopf} text-right`}>
                  gezeigt
                </th>
                <th scope="col" className={`${kopf} text-right`}>
                  laut dieser Lieferung
                </th>
                <th scope="col" className={`${kopf} text-right`}>
                  Differenz
                </th>
                <th scope="col" className={`${kopf} pr-0`}>
                  Hauptursache
                </th>
              </tr>
            </thead>
            <tbody>
              {zeilen.map((z) => (
                <tr key={z.berichtsmonat} className="border-b border-line">
                  <th scope="row" className={`${zelle} text-left font-medium`}>
                    {monatName(z.berichtsmonat)}
                  </th>
                  <td className={zahlZelle}>
                    {formatZahl(z.veroeffentlicht)}
                    {z.vorlaeufig && <span className="block font-sans text-12 text-slate">vorläufig</span>}
                  </td>
                  <td className={zahlZelle}>{formatZahl(z.aktuell)}</td>
                  <td className={zahlZelle}>{formatDifferenz(z.differenz)}</td>
                  <td className={`${zelle} pr-0`}>{z.hauptursache ?? "nicht ermittelt"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <ul className="flex flex-col md:hidden" aria-label="Revisionsbedarf">
            {zeilen.map((z) => (
              <li key={z.berichtsmonat} className="flex flex-col gap-1 border-b border-line py-4">
                <p className="font-sans text-16 font-semibold text-ink">{monatName(z.berichtsmonat)}</p>
                <p className="font-sans text-14 text-ink">
                  {"gezeigt "}
                  <span className="font-mono tabular-nums">{formatZahl(z.veroeffentlicht)}</span>
                  {", jetzt "}
                  <span className="font-mono tabular-nums">{formatZahl(z.aktuell)}</span>
                  {", Differenz "}
                  <span className="font-mono tabular-nums">{formatDifferenz(z.differenz)}</span>
                </p>
                <p className="font-sans text-12 text-slate">{`Hauptursache: ${z.hauptursache ?? "nicht ermittelt"}`}</p>
              </li>
            ))}
          </ul>
        </>
      )}
    </Abschnitt>
  );
}
