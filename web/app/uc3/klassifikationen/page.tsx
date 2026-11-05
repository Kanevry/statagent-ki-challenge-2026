import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { Fliesstext, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { formatZahl } from "@kic/ui/bausteine";
import { BelegLink, StandPunkt } from "@/components/uc3/beleg-link";
import { leseRegeln, REGEL_TYPEN, sqlRegeln, type Regel, type RegelTyp } from "@/components/uc3/bericht";
import { DatenFehler } from "@/components/uc3/daten-fehler";
import { leerSatz } from "@/components/uc3/db";
import {
  datumLang,
  gegenueberSaetze,
  gegenueberstellung,
  leseKlassifikationen,
  qualifikationsStaende,
  regelKlartext,
  SQL_ALTERSGRUPPEN,
  SQL_BUNDESLAENDER,
  SQL_GESCHLECHT,
  SQL_QUALIFIKATIONEN,
  sqlAbschnitte,
  sqlAbschnittUebergaenge,
  sqlKategorieAuftrag,
  sqlKategorieRegel,
  type Klassifikationsdaten,
} from "@/components/uc3/klassifikation";
import { leseNachschlagen, SQL_NACHSCHLAGEN } from "@/components/uc3/klassifikation-tief";
import { monatName } from "@/components/uc3/monat";
import { lesePensionen, SQL_PENSIONEN } from "@/components/uc3/pensionen";
import { regelsatzAus, uebersichtPfad, type Regelsatz } from "@/components/uc3/navigation";
import { alltag } from "@/components/uc3/sprache";
import { Gegenueberstellung } from "./_teile/gegenueberstellung";
import { Nachschlagen } from "./_teile/nachschlagen";

// Regeln und Klassifikationen (UI-Regie v1, #18): oben ÖNACE 2008 gegen 2025 als Gegenüberstellung nach Namen,
// darunter das Nachschlagen bis zur Unterklasse und Gemeinde, die Qualifikationen je Regelsatz, dann alle Regeln nach Art (Anker #regeln, Ziel von
// /uc3/berichte/regeln). Die kleinen Code-Listen liegen hinter „Weitere Listen“. Nur lesend; ohne Datenbank zeigt
// jeder Teil seinen Leerzustand (HTTP 200).
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Regeln und Klassifikationen · StatAgent" };

type Props = { searchParams: Promise<{ regelsatz?: string | string[] }> };

const titel = "font-sans text-16 font-semibold text-ink";
const textLink = "inline-flex min-h-11 items-center font-sans text-14 text-ink underline underline-offset-4 hover:text-gruen";

function pfad(regelsatz: Regelsatz): string {
  return `/uc3/klassifikationen${regelsatz === "v1" ? "" : `?regelsatz=${regelsatz}`}#regeln`;
}

// ---------------------------------------------------------------------------------------------------------------
// ÖNACE 2008 → 2025 und Qualifikationen

function Branchen({ daten }: { daten: Klassifikationsdaten }) {
  const zeilen = gegenueberstellung(daten.abschnitte, daten.abschnittUebergaenge);
  const saetze = gegenueberSaetze(zeilen);
  return (
    <>
      <header className="flex max-w-4xl flex-col gap-3">
        <Ueberschrift stufe={2} als="h1" className="hyphens-auto break-words">
          {saetze.haupt}
        </Ueberschrift>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="font-sans text-16 text-slate">{saetze.unter}</span>
          <span className="font-sans text-14 text-slate">
            Neuen Namen und Teilung ordnet die Seite aus dem Umsteigeschlüssel zu: Nachfolger ist, wer mindestens ein
            Viertel der Unterklassen bekommt.
          </span>
          <BelegLink
            quelle="stat.klass_oenace, stat.uebergang"
            verweis="Gezählt je Branchenname; neuer Name und Teilung aus dem Umsteigeschlüssel (Nachfolger mit mindestens 25 % der Unterklassen)"
            sql={`-- Abschnitte beider Fassungen, daraus gleich und anderer Buchstabe je Name\n${sqlAbschnitte()}\n\n-- Umsteigeschlüssel je Abschnitt, daraus neuer Name und Teilung\n${sqlAbschnittUebergaenge()}`}
          />
        </div>
      </header>

      <a href="#regeln" className={`${textLink} self-start`}>
        Zu den Regeln
      </a>

      <section aria-labelledby="branchen-titel" className="flex flex-col gap-3">
        <h2 id="branchen-titel" className={titel}>
          Branchen 2008 und 2025
        </h2>
        <Gegenueberstellung zeilen={zeilen} />
        <div className="flex max-w-4xl flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="font-sans text-14 text-slate">
            {daten.abschnittUebergaenge.length > 0
              ? "Neue Namen und Teilungen kommen aus dem Umsteigeschlüssel von Statistik Austria."
              : "Der Umsteigeschlüssel von ÖNACE 2008 auf 2025 ist noch nicht geladen."}
          </span>
          <BelegLink quelle="stat.uebergang" sql={`${sqlAbschnitte()}\n\n${sqlAbschnittUebergaenge()}`} />
        </div>
      </section>
    </>
  );
}

async function AlleCodes() {
  const lesung = await leseNachschlagen();
  // Wie bei den Pensionen: Sind die tiefen Ebenen nicht geladen, gibt es hier nichts zu zeigen.
  if (!lesung.ok || !lesung.daten) return null;
  const { auswahl, start, art } = lesung.daten;
  return (
    <section aria-labelledby="codes-titel" className="flex max-w-4xl flex-col gap-3">
      <h2 id="codes-titel" className={titel}>
        Alle Codes bis zur Unterklasse und Gemeinde
      </h2>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-sans text-14 text-slate">
          Die Statistik zählt nach Abschnitt und Bundesland. Für die Ebenen darunter gibt es hier die Namen, keine Zahlen.
        </span>
        <BelegLink quelle="stat.klass_oenace, stat.klass_region, stat.uebergang" sql={SQL_NACHSCHLAGEN} />
      </div>
      <Nachschlagen auswahl={auswahl} start={start} startArt={art} />
    </section>
  );
}

function Qualifikationen({ daten }: { daten: Klassifikationsdaten }) {
  const stand = daten.kategorieStand;
  if (!stand) return null;
  const staende = qualifikationsStaende(stand, daten.qualifikationen);
  const sql = stand.auftrag ? `${sqlKategorieRegel(stand.regelsatz)}\n\n${sqlKategorieAuftrag(stand)}` : sqlKategorieRegel(stand.regelsatz);
  return (
    <section aria-labelledby="qualifikation-titel" className="flex max-w-4xl flex-col gap-2">
      <h2 id="qualifikation-titel" className={titel}>
        Qualifikationen je Regelsatz
      </h2>
      <ul className="flex flex-col">
        {staende.map((s) => (
          <li key={s.regelsatz} className="flex flex-col gap-1 border-b border-line py-3">
            <p className="max-w-3xl font-sans text-16 text-ink">{s.satz}</p>
            <div className="flex flex-wrap items-center gap-x-4">
              {s.status && (
                <StandPunkt
                  stand={s.status}
                  wort={s.freigabe ?? (s.status === "offen" ? "wartet auf Freigabe" : undefined)}
                  className="text-slate"
                />
              )}
              {s.auftrag && (
                <Link href={`/uc3/freigaben/${s.auftrag.vorschlagId}`} className={textLink}>
                  {`${s.auftrag.titel} ansehen`}
                </Link>
              )}
            </div>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        {staende.length > 1 && (
          <span className="font-sans text-14 text-slate">
            {`Die Monate sind mit Regelsatz ${stand.regelsatz} gerechnet. Regelsatz ${staende[1]!.regelsatz} zeigen Sie mit dem Umschalter auf der Seite `}
            <Link href={uebersichtPfad(staende[1]!.regelsatz)} className="text-ink underline underline-offset-4 hover:text-gruen">
              Läufe
            </Link>
            .
          </span>
        )}
        <BelegLink quelle="meta.regel" sql={sql} />
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------------------------------------------
// Regeln

const GRUPPEN: Record<RegelTyp, string> = {
  einlese: "Einlesen",
  zuordnung: "Zuordnen",
  zaehl: "Zählen",
  pruefung: "Prüfen",
};

function gueltigkeit(r: Regel): string {
  return r.gueltigBis
    ? `von ${monatName(r.gueltigAb)} bis ${monatName(r.gueltigBis)}`
    : `ab der Lieferung ${monatName(r.gueltigAb)}`;
}

function Angabe({ wort, children }: { wort: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="font-sans text-12 text-slate">{wort}</dt>
      <dd className="font-sans text-14 text-ink">{children}</dd>
    </div>
  );
}

function Regelpunkt({ regel }: { regel: Regel }) {
  return (
    <li id={regel.name} data-regel={regel.name} className="flex scroll-mt-24 flex-col gap-1 border-b border-line py-3">
      <p className="max-w-3xl font-sans text-16 text-ink">{regelKlartext(regel.beschreibung)}</p>
      <div className="flex flex-wrap items-center gap-x-4">
        {regel.freigegebenVon ? (
          <StandPunkt
            stand="freigegeben"
            wort={`freigegeben von ${regel.freigegebenVon}${regel.freigegebenAm ? ` am ${datumLang(regel.freigegebenAm)}` : ""}`}
            className="text-slate"
          />
        ) : (
          <StandPunkt stand="offen" wort="noch ohne Freigabe" className="text-slate" />
        )}
        <details className="group">
          <summary className="inline-flex min-h-11 cursor-pointer list-none items-center font-sans text-14 text-slate underline decoration-line underline-offset-4 hover:text-ink [&::-webkit-details-marker]:hidden">
            Begründung und Grundlage
          </summary>
          <dl className="mb-2 flex max-w-3xl flex-col gap-2 border-l border-line pl-4">
            <Angabe wort="Ganze Regel">{alltag(regel.beschreibung)}</Angabe>
            <Angabe wort="Begründung">{alltag(regel.begruendung)}</Angabe>
            <Angabe wort="Grundlage">{alltag(regel.grundlage)}</Angabe>
            <Angabe wort="Gilt">{gueltigkeit(regel)}</Angabe>
            <Angabe wort="Name in der Datenbank">{regel.name}</Angabe>
          </dl>
        </details>
      </div>
    </li>
  );
}

function RegelsatzWahl({ aktiv }: { aktiv: Regelsatz }) {
  const punkte: Array<[Regelsatz, string]> = [
    ["v1", "Regelsatz v1: nach der Fachbeschreibung."],
    ["v2", "Regelsatz v2: mit den freigegebenen Änderungsaufträgen."],
  ];
  return (
    <nav aria-label="Regelsatz" className="flex items-center gap-2 font-sans text-14 text-slate">
      <span>Regelsatz</span>
      <ul className="flex overflow-hidden rounded-md border border-line">
        {punkte.map(([wert, erklaerung]) => (
          <li key={wert}>
            <Link
              href={pfad(wert)}
              title={erklaerung}
              aria-current={wert === aktiv ? "page" : undefined}
              className={`inline-flex min-h-11 min-w-11 items-center justify-center px-3 ${wert === aktiv ? "bg-ink text-white" : "text-ink hover:bg-paper"}`}
            >
              {wert}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

async function Regeln({ regelsatz }: { regelsatz: Regelsatz }) {
  const lesung = await leseRegeln(regelsatz);
  const regeln = lesung.ok ? lesung.daten : [];
  const freigegeben = regeln.filter((r) => r.freigegebenVon).length;
  const freigabe =
    freigegeben === regeln.length
      ? "Alle sind mit Namen freigegeben."
      : freigegeben === 0
        ? "Noch keine ist mit Namen freigegeben."
        : `${formatZahl(freigegeben)} davon ${freigegeben === 1 ? "ist" : "sind"} mit Namen freigegeben.`;

  return (
    <section id="regeln" aria-labelledby="regeln-titel" className="flex max-w-4xl scroll-mt-24 flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <Ueberschrift stufe={3} als="h2" id="regeln-titel">
          Regeln
        </Ueberschrift>
        <RegelsatzWahl aktiv={regelsatz} />
      </div>
      {regeln.length === 0 ? (
        <Leerzustand
          satz={lesung.ok ? `Für den Regelsatz ${regelsatz} ist noch keine Regel angelegt.` : leerSatz(lesung.grund)}
        />
      ) : (
        <>
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <Fliesstext className="max-w-3xl">
              {`${formatZahl(regeln.length)} Regeln bestimmen in Regelsatz ${regelsatz}, wie wir einlesen, zuordnen, zählen und prüfen. ${freigabe} Jede Regel steht in der Datenbank, nicht im Programmcode.`}
            </Fliesstext>
            <BelegLink quelle="meta.regel" regelstand={`Regelsatz ${regelsatz}`} sql={sqlRegeln(regelsatz)} />
          </div>
          {REGEL_TYPEN.map((typ) => {
            const gruppe = regeln.filter((r) => r.typ === typ);
            if (gruppe.length === 0) return null;
            return (
              <details key={typ} className="group border-b border-line">
                <summary className="flex min-h-11 cursor-pointer list-none items-baseline gap-2 py-3 font-sans text-16 font-semibold text-ink [&::-webkit-details-marker]:hidden">
                  <h3 id={`gruppe-${typ}`} className="font-sans text-16 font-semibold text-ink">
                    {GRUPPEN[typ]}
                  </h3>
                  <span className="font-normal tabular-nums text-slate">{`${formatZahl(gruppe.length)} ${gruppe.length === 1 ? "Regel" : "Regeln"}`}</span>
                  <span aria-hidden="true" className="ml-auto text-slate transition-transform group-open:rotate-90">
                    ›
                  </span>
                </summary>
                <ul className="flex flex-col pb-2">
                  {gruppe.map((r) => (
                    <Regelpunkt key={r.id} regel={r} />
                  ))}
                </ul>
              </details>
            );
          })}
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------------------------------------------
// Weitere Listen

function Liste({ titel: name, quelle, sql, children }: { titel: string; quelle: string; sql: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2 border-b border-line py-3 last:border-b-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <h3 className="font-sans text-14 font-semibold text-ink">{name}</h3>
        <BelegLink quelle={quelle} sql={sql} />
      </div>
      {children}
    </div>
  );
}

function WeitereListen({ daten }: { daten: Klassifikationsdaten }) {
  const { bundeslaender, geschlechter, qualifikationen, altersgruppen } = daten;
  return (
    <details className="max-w-4xl border-y border-line">
      <summary className="flex min-h-11 cursor-pointer items-center font-sans text-16 text-ink underline-offset-4 hover:underline">
        Weitere Listen: Bundesland, Geschlecht, Qualifikation und Alter
      </summary>
      <div className="flex flex-col pb-3">
        <Liste titel={`Bundesland, ${bundeslaender.length} Codes`} quelle="stat.klass_region" sql={SQL_BUNDESLAENDER}>
          <ul className="grid grid-cols-1 gap-x-8 gap-y-1 sm:grid-cols-2">
            {bundeslaender.map((b) => (
              <li key={b.code} className="flex gap-3 font-sans text-14 text-ink">
                <span className="w-8 shrink-0 text-right tabular-nums text-slate">{b.code}</span>
                <span>{b.bezeichnung}</span>
              </li>
            ))}
          </ul>
        </Liste>
        <Liste titel={`Geschlecht, ${geschlechter.length} Codes`} quelle="stat.klass_geschlecht" sql={SQL_GESCHLECHT}>
          <ul className="flex flex-col gap-1">
            {geschlechter.map((g) => (
              <li key={g.code} className="flex gap-3 font-sans text-14 text-ink">
                <span className="w-8 shrink-0 text-right text-slate">{g.code}</span>
                <span>{g.bezeichnung}</span>
              </li>
            ))}
          </ul>
        </Liste>
        <Liste titel={`Qualifikation, ${qualifikationen.length} Codes`} quelle="stat.klass_qualifikation" sql={SQL_QUALIFIKATIONEN}>
          <ul className="flex flex-col gap-1">
            {qualifikationen.map((q) => (
              <li key={q.code} className="flex flex-col font-sans text-14 sm:flex-row sm:gap-3">
                <span className="text-ink sm:flex-1">{q.bezeichnung}</span>
                <span className="text-slate">{`Beschäftigungskategorie ${q.kategorie}`}</span>
              </li>
            ))}
          </ul>
        </Liste>
        <Liste titel={`Alter, ${altersgruppen.length} Gruppen`} quelle="stat.klass_alter" sql={SQL_ALTERSGRUPPEN}>
          <ul className="flex flex-wrap gap-x-4 gap-y-1">
            {altersgruppen.map((g) => (
              <li key={g.gruppe} className="font-sans text-14 text-ink">
                {g.gruppe}
              </li>
            ))}
          </ul>
        </Liste>
      </div>
    </details>
  );
}

// ---------------------------------------------------------------------------------------------------------------

async function Pensionen() {
  const lesung = await lesePensionen();
  // Ohne Datenbank oder vor dem Laden gibt es hier nichts zu zeigen, und online kann niemand laden.
  if (!lesung.ok || lesung.daten.jahre.length === 0) return null;
  const { jahre, vorlaeufig } = lesung.daten;
  return (
    <details className="max-w-4xl border-b border-line">
      <summary className="flex min-h-11 cursor-pointer items-center font-sans text-16 text-ink underline-offset-4 hover:underline">
        Pensionen 2018 bis 2025
      </summary>
      <div className="flex flex-col gap-2 pb-3">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
          <Fliesstext>
            Durchschnitt je Jahr aus den Meldungen der Träger{vorlaeufig ? ", vorläufig" : ""}. Die vorzeitigen
            Alterspensionen sind in „Insgesamt“ enthalten. Zum 1. Jänner 2020 wurden Träger zusammengelegt. Die Zahlen davor
            und danach stehen unverändert nebeneinander.
          </Fliesstext>
          <BelegLink quelle="stat.stat_pensionen" sql={SQL_PENSIONEN} />
        </div>
        <table className="w-full font-sans text-14 text-ink">
          <thead>
            <tr className="border-b border-line text-left text-slate">
              <th scope="col" className="py-1 pr-2 font-normal">Jahr</th>
              <th scope="col" className="py-1 pr-2 text-right font-normal">Insgesamt</th>
              <th scope="col" className="py-1 pr-2 text-right font-normal">{"Un\u00adselbst\u00adändige"}</th>
              <th scope="col" className="py-1 pr-2 text-right font-normal">{"Selbst\u00adändige"}</th>
              <th scope="col" className="py-1 text-right font-normal">{"Vor\u00adzeitige"}</th>
            </tr>
          </thead>
          <tbody>
            {jahre.map((j) => (
              <tr key={j.jahr} className="border-b border-line last:border-b-0">
                <th scope="row" className="py-1 pr-2 text-left font-normal">{j.jahr}</th>
                <td className="py-1 pr-2 text-right tabular-nums">{formatZahl(j.insgesamt)}</td>
                <td className="py-1 pr-2 text-right tabular-nums">{formatZahl(j.unselbstaendige)}</td>
                <td className="py-1 pr-2 text-right tabular-nums">{formatZahl(j.selbstaendige)}</td>
                <td className="py-1 text-right tabular-nums">{formatZahl(j.vorzeitig)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Fliesstext>
          Öffentlich Bedienstete fehlen in allen Jahren, die frühere BVA meldet keine Pensionen. Bei „Vorzeitige“ fehlt 2018 und
          2019 das Notariat, es meldet diese Art nicht.
        </Fliesstext>
      </div>
    </details>
  );
}

export default async function RegelnUndKlassifikationen({ searchParams }: Props) {
  const regelsatz = regelsatzAus((await searchParams).regelsatz);
  // Die Klassifikationen hängen nicht am Regelsatz; der Auftrag für die Qualifikationen geht von v1 aus.
  const lesung = await leseKlassifikationen("v1");
  if (!lesung.ok) return <DatenFehler grund={lesung.grund} />;
  const daten = lesung.daten.abschnitte.length > 0 ? lesung.daten : null;

  return (
    <>
      {daten ? (
        <>
          <Branchen daten={daten} />
          <AlleCodes />
          <Qualifikationen daten={daten} />
          <Pensionen />
        </>
      ) : (
        <header className="flex max-w-4xl flex-col gap-3">
          <Ueberschrift stufe={2} als="h1">
            Regeln und Klassifikationen
          </Ueberschrift>
          <Leerzustand
            satz="Die Code-Listen sind noch nicht geladen. Sie kommen mit dem Startpaket in die Datenbank."
          />
        </header>
      )}
      <Regeln regelsatz={regelsatz} />
      {daten && <WeitereListen daten={daten} />}
    </>
  );
}
