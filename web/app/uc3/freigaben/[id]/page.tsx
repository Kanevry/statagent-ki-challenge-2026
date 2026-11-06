import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { formatDifferenz, formatZahl, type FreigabeEntscheidung } from "@kic/ui/bausteine";
import { literal, type Beleg } from "@/components/uc3/beleg";
import { BelegLink, StandPunkt } from "@/components/uc3/beleg-link";
import { vorfuehrungOffen } from "@/components/uc3/auftrag";
import { nurLesend } from "@/components/uc3/cli";
import { DatenFehler } from "@/components/uc3/daten-fehler";
import { MinisteriumListe } from "@/components/uc3/ministerium-liste";
import {
  aenderungKurz,
  auftraggeber,
  auftragKopf,
  auftragsZitat,
  ergebnisPfad,
  klartext,
  kurzZeit,
  klarerAenderungsSatz,
  leseVorschlag,
  ohneProbeSatz,
  ohneProbeTitel,
  probeAendert,
  probeJeKategorie,
  zitatDoppelt,
  zitatTeile,
  probeTabelleBeleg,
  probeTitel,
  probeWirkungSatz,
  regionenSatz,
  sqlErgebnisLauf,
  sqlWirkung,
  vorgeschlagenVon,
  vorschlagId,
  wirkungJeKategorie,
  type EchteWirkung,
  type Kategorien,
  type ProbeTabelle,
  type Bezeichnungen,
  type Vorschlag,
} from "@/components/uc3/freigabe";
import { monatName } from "@/components/uc3/monat";
import { mitRegeln, regelsatzName } from "@/components/uc3/regelsatz-name";
import { Entscheiden } from "./entscheiden";

// Ein Vorschlag (UI-Regie v1): oben der Auftrag im Wortlaut, in der Mitte die Probe als kleine Tabelle vorher und
// nachher mit einem Beleg, unten die Freigabe (lokal das Formular, online nur der Satz). Vergleich der Regelsätze aus
// echten Läufen, die Regeländerung und die Begründung des Agenten stehen hinter „Details“.
// Liest die UC3-Datenbank direkt; ohne Datenbank Leerzustand mit HTTP 200, unbekannte ID → 404.
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Freigaben · StatAgent" };

function entscheidungAus(v: Vorschlag): FreigabeEntscheidung | undefined {
  if (v.status === "freigegeben" && v.freigegebenVon && v.freigegebenAm)
    return { art: "freigegeben", name: v.freigegebenVon, zeit: v.freigegebenAm };
  if (v.status === "abgelehnt" && v.abgelehntVon && v.abgelehntAm)
    return { art: "abgelehnt", name: v.abgelehntVon, zeit: v.abgelehntAm, begruendung: v.ablehnungsgrund ?? "" };
  return undefined;
}

/** Beleg der Regeländerung selbst: Wortlaut und Regelname stehen hier, nicht im Fließtext. */
function aenderungBeleg(v: Vorschlag, bezeichnungen: Bezeichnungen): Beleg {
  const { worte } = klartext(v, bezeichnungen);
  return {
    quelle: "meta.vorschlag",
    verweis: `Vorschlag uc3/${v.id}, ${aenderungKurz(v)}`,
    zitat: worte.join(" ") || undefined,
    sql: `SELECT typ, regelsatz_basis, regelsatz_ziel, aenderungen\nFROM meta.vorschlag\nWHERE id = ${literal(v.id)};`,
  };
}

const zelle = "py-2 pr-6 text-right font-sans tabular-nums";
const kopfZelle = "py-2 pr-6 text-right font-sans text-14 font-medium text-slate";

export default async function FreigabeSeite({ params }: { params: Promise<{ id: string }> }) {
  const id = vorschlagId((await params).id);
  if (id === null) notFound();
  const lesung = await leseVorschlag(id);

  if (!lesung.ok) return <DatenFehler grund={lesung.grund} />;
  const { vorschlag: v, kategorien, ergebnis, wirkung, bezeichnungen } = lesung.daten;
  if (!v) notFound();

  const kopf = auftragKopf(v.anweisung);
  const zitat = zitatTeile(auftragsZitat(v.anweisung));
  const klarerSatz = klarerAenderungsSatz(v, bezeichnungen);
  const quelle = kopf.nummer ? `Änderungsauftrag ${kopf.nummer} aus der Aufgabenstellung` : auftraggeber(v);
  const gesagtAm = v.gesagtAm ?? v.erstelltAm;
  const tabelle = probeJeKategorie(v.probe, kategorien);
  const regionen = regionenSatz(v.probe, bezeichnungen);
  const entscheidung = entscheidungAus(v);

  return (
    <>
      <nav aria-label="Zurück">
        <Link
          href="/uc3/freigaben"
          className="inline-flex min-h-11 items-center font-sans text-14 font-medium text-gruen underline underline-offset-4"
        >
          Alle Freigaben
        </Link>
      </nav>

      <header className="flex max-w-3xl flex-col gap-4">
        <Ueberschrift stufe={2} als="h1" className="hyphens-auto break-words">
          {kopf.titel}
        </Ueberschrift>
        <figure className="flex flex-col gap-2">
          {/* Steht der ganze Auftrag schon in der Überschrift, wäre das Zitat derselbe Satz noch einmal. */}
          {!zitatDoppelt(kopf.titel, auftragsZitat(v.anweisung)) && (
            <blockquote className="font-sans text-20 text-pretty text-ink">{`„${zitat.anfang}“`}</blockquote>
          )}
          {zitat.rest && !zitatDoppelt(kopf.titel, auftragsZitat(v.anweisung)) && (
            <details>
              <summary className="inline-flex min-h-11 cursor-pointer items-center font-sans text-14 text-slate underline decoration-line underline-offset-4">
                Ganzer Auftrag
              </summary>
              <p className="font-sans text-16 text-pretty text-ink">{`„${zitat.rest}“`}</p>
            </details>
          )}
          <figcaption className="font-sans text-14 text-slate">
            {`${quelle}, `}
            <time dateTime={gesagtAm} className="tabular-nums">
              {kurzZeit(gesagtAm)}
            </time>
          </figcaption>
        </figure>
        {klarerSatz && <p className="font-sans text-16 font-semibold text-pretty text-ink">{klarerSatz}</p>}
      </header>

      {wirkung && tabelle && probeAendert(tabelle).gesamt && <WirkungOben wirkung={wirkung} />}

      <section aria-labelledby="probe-titel" className="flex max-w-3xl flex-col gap-3">
        <h2 id="probe-titel" className="font-sans text-16 font-semibold text-ink">
          {tabelle ? probeTitel(tabelle.lieferung) : ohneProbeTitel(v)}
        </h2>
        <p className="font-sans text-14 text-slate">{`${vorgeschlagenVon(v)}.`}</p>
        {regionen && <p className="font-sans text-16 font-semibold text-ink">{regionen}</p>}
        {tabelle ? (
          <ProbeTabelleAnsicht vorschlag={v.id} tabelle={tabelle} wirkung={regionen ? null : probeWirkungSatz(v.probe, bezeichnungen)} />
        ) : (
          <p className="font-sans text-16 text-ink">{ohneProbeSatz(v)}</p>
        )}
      </section>

      <section aria-labelledby="freigabe-titel" className="flex max-w-3xl flex-col gap-4 border-t border-line pt-6">
        <h2 id="freigabe-titel" className="sr-only">
          Freigabe
        </h2>
        <Entscheiden
          vorschlagId={v.id}
          entscheidung={entscheidung}
          entschiedenAm={entscheidung ? kurzZeit(entscheidung.zeit) : undefined}
          nurLesen={nurLesend()}
        />
        {vorfuehrungOffen() && v.commitHash && (
          <p className="font-sans text-14 text-slate">
            {"Im Protokoll als Commit "}
            <span className="font-mono tabular-nums text-ink">{v.commitHash.slice(0, 10)}</span>
            {", mit dem Namen der Person, die freigegeben hat."}
          </p>
        )}
        {ergebnis && v.status === "freigegeben" && (
          <div className="flex flex-col gap-2">
            {ergebnis.laufDa ? (
              <div>
                <Link
                  href={ergebnisPfad(ergebnis)}
                  className="inline-flex min-h-11 items-center font-sans text-16 font-medium text-gruen underline underline-offset-4"
                >
                  {`Ergebnis für ${monatName(ergebnis.monat)} ${mitRegeln(ergebnis.regelsatz)} ansehen`}
                </Link>
              </div>
            ) : (
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="font-sans text-16 text-ink">
                  {`Die neuen Zahlen für ${monatName(ergebnis.monat)} entstehen, wenn der Stand „${regelsatzName(ergebnis.regelsatz)}“ Monat für Monat bis dorthin gerechnet ist.`}
                </span>
                <BelegLink
                  quelle="meta.lauf"
                  lieferung={ergebnis.monat}
                  stand="vorlaeufig"
                  sql={sqlErgebnisLauf(ergebnis.monat, ergebnis.regelsatz)}
                />
              </div>
            )}
          </div>
        )}
      </section>

      {v.regelsatzZiel === "ministerium" && v.status === "freigegeben" && (
        <section aria-labelledby="liste-titel" className="flex max-w-3xl flex-col gap-3 border-t border-line pt-6">
          <h2 id="liste-titel" className="font-sans text-16 font-semibold text-ink">
            Die Liste für das Ministerium
          </h2>
          <MinisteriumListe />
          <div>
            <Link
              href="/uc3/ergebnisse"
              className="inline-flex min-h-11 items-center font-sans text-14 font-medium text-gruen underline underline-offset-4"
            >
              Excel-Dateien der Abgabe herunterladen
            </Link>
          </div>
        </section>
      )}

      <details className="max-w-3xl">
        <summary className="inline-flex min-h-11 cursor-pointer items-center font-sans text-14 text-slate underline decoration-line underline-offset-4 hover:text-ink">
          Details
        </summary>
        <div className="mt-2 flex flex-col gap-6">
          {wirkung && <WirkungTeil wirkung={wirkung} kategorien={kategorien} />}
          <DetailBlock titel="Begründung des Agenten">
            <p className="font-sans text-16 text-pretty text-ink">{v.begruendung}</p>
          </DetailBlock>
          <DetailBlock titel="Die Regeländerung">
            <div>
              <BelegLink {...aenderungBeleg(v, bezeichnungen)} text="Regeländerung ansehen" />
            </div>
          </DetailBlock>
        </div>
      </details>
    </>
  );
}

function DetailBlock({ titel, children }: { titel: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="font-sans text-14 font-semibold text-ink">{titel}</h3>
      {children}
    </div>
  );
}

/**
 * Probe als Tabelle (UI-Regie v1): links vorher die getrennt gezählten Gruppen (Dienstvertrag und freier
 * Dienstvertrag), rechts nachher die zusammengefasste Kategorie. So sieht man, was die Änderung tut, obwohl die
 * Gesamtzahl gleich bleibt. Ein Beleg für die ganze Tabelle.
 */
function ProbeTabelleAnsicht({ vorschlag, tabelle: t, wirkung }: { vorschlag: number; tabelle: ProbeTabelle; wirkung: string | null }) {
  const kopf = "py-2 text-left font-sans text-14 font-medium text-slate";
  // Am Handy enger: Die vier Spalten müssen in 358 px passen, sonst ist die Spalte „nachher“ abgeschnitten.
  const wort = "py-2 pr-2 text-left font-sans text-14 font-normal text-ink sm:pr-4 sm:text-16";
  const zahlZ = "py-2 pr-2 text-right font-sans text-14 tabular-nums text-ink sm:pr-6 sm:text-16";
  const aendert = probeAendert(t);
  return (
    <div className="flex flex-col gap-2">
      <div className="overflow-x-auto">
      <table className="w-full max-w-2xl border-collapse">
        <caption className="sr-only">{`${probeTitel(t.lieferung)}: Beschäftigungsverhältnisse vorher und nachher`}</caption>
        <thead>
          <tr className="border-b border-line">
            <th scope="col" colSpan={2} className={kopf}>
              vorher
            </th>
            <th scope="col" colSpan={2} className={`${kopf} border-l border-line pl-2 sm:pl-4`}>
              nachher
            </th>
          </tr>
        </thead>
        <tbody>
          {t.zeilen.flatMap((z) => {
            const teile = z.vorherTeile.length > 0 ? z.vorherTeile : [{ wort: z.kategorie, wert: z.vorher }];
            return teile.map((teil, i) => (
              <tr key={`${z.kategorie}-${teil.wort}`} className={i === teile.length - 1 ? "border-b border-line" : ""}>
                <td className={wort}>{teil.wort}</td>
                <td className={zahlZ}>{formatZahl(teil.wert)}</td>
                {i === 0 && (
                  <>
                    <th scope="row" rowSpan={teile.length} className={`${wort} border-l border-line pl-2 sm:pl-4 align-middle`}>
                      {z.kategorie}
                    </th>
                    <td rowSpan={teile.length} className={`${zahlZ} pr-0 align-middle`}>
                      {formatZahl(z.nachher)}
                    </td>
                  </>
                )}
              </tr>
            ));
          })}
          <tr className="font-semibold">
            <td className={`${wort} font-semibold`}>Gesamt</td>
            <td className={`${zahlZ} font-semibold`}>{formatZahl(t.gesamt.vorher)}</td>
            <td className={`${wort} border-l border-line pl-2 sm:pl-4 font-semibold`}>Gesamt</td>
            <td className={`${zahlZ} pr-0 font-semibold`}>{formatZahl(t.gesamt.nachher)}</td>
          </tr>
        </tbody>
      </table>
      </div>
      <div className="flex flex-wrap items-baseline gap-x-4">
        <span className="font-sans text-16 text-ink">
          {aendert.gesamt
            ? `Gesamt ändert sich in diesem Monat um ${formatDifferenz(t.gesamt.nachher - t.gesamt.vorher)}.`
            : aendert.gliederung
              ? "Gesamt bleibt gleich, nur die Gliederung ändert sich."
              : "Bei den Beschäftigungskategorien ändert die Testrechnung keine Zahl, die Gesamtzahl bleibt gleich."}
        </span>
        <BelegLink {...probeTabelleBeleg(vorschlag, t)} />
      </div>
      {!aendert.gesamt && !aendert.gliederung && wirkung && <p className="font-sans text-16 text-ink">{wirkung}</p>}
    </div>
  );
}

/** Die Zahl, um die es geht, gleich sichtbar statt unter „Details“: der jüngste Monat mit fertigem Lauf in beiden Ständen. */
function WirkungOben({ wirkung: e }: { wirkung: EchteWirkung }) {
  const unterschied = e.ziel.gesamt - e.basis.gesamt;
  if (unterschied === 0) return null;
  return (
    <section aria-labelledby="wirkung-titel" className="flex max-w-3xl flex-col gap-2">
      <h2 id="wirkung-titel" className="font-sans text-16 font-semibold text-ink">
        {`Das ändert sich im ${monatName(e.monat)}`}
      </h2>
      <p className="flex flex-wrap items-baseline gap-x-3 font-sans tabular-nums text-ink">
        <span className="text-20">{formatZahl(e.basis.gesamt)}</span>
        <span aria-hidden="true" className="text-20 text-slate">
          →
        </span>
        <span className="sr-only">wird zu</span>
        <span className="text-32 font-semibold">{formatZahl(e.ziel.gesamt)}</span>
        <span className="text-20 font-medium text-gruen">{formatDifferenz(unterschied)}</span>
      </p>
      <p className="font-sans text-14 text-slate">{`Beschäftigungsverhältnisse ${mitRegeln(e.basis.lauf.regelsatz)} und ${mitRegeln(e.ziel.lauf.regelsatz)}. Die Tabelle dazu steht unter „Details“.`}</p>
    </section>
  );
}

/** Vergleich der Regelsätze aus echten Läufen: je Kategorie und Gesamt, der jüngste Monat mit beiden Läufen. */
function WirkungTeil({ wirkung: e, kategorien }: { wirkung: EchteWirkung; kategorien: Kategorien }) {
  const rb = e.basis.lauf.regelsatz;
  const rz = e.ziel.lauf.regelsatz;
  const zeilen = wirkungJeKategorie(e, kategorien).sort((a, b) => a.kategorie.localeCompare(b.kategorie, "de"));
  const beleg: Beleg = {
    quelle: "stat.stat_beschaeftigte",
    lieferung: e.monat,
    monat: e.monat,
    regelstand: `${regelsatzName(rb)}: ${e.basis.lauf.regelstand}, ${regelsatzName(rz)}: ${e.ziel.lauf.regelstand}`,
    verweis: "Jüngster Monat mit fertigem Lauf in beiden Ständen",
    sql: [`-- ${regelsatzName(rb)}`, sqlWirkung(e.basis.lauf), "", `-- ${regelsatzName(rz)}`, sqlWirkung(e.ziel.lauf)].join("\n"),
  };
  return (
    <DetailBlock titel={`${monatName(e.monat)}, beide Stände gerechnet`}>
      <div className="overflow-x-auto">
      <table className="w-full max-w-lg border-collapse">
        <caption className="sr-only">{`Beschäftigungsverhältnisse ${monatName(e.monat)} ${mitRegeln(rb)} und ${mitRegeln(rz)}`}</caption>
        <thead>
          <tr className="border-b border-line">
            <th scope="col" className="py-2 pr-6 text-left">
              <span className="sr-only">Kategorie</span>
            </th>
            <th scope="col" className={kopfZelle}>{regelsatzName(rb)}</th>
            <th scope="col" className={kopfZelle}>{regelsatzName(rz)}</th>
            <th scope="col" className={kopfZelle}>
              Unterschied
            </th>
          </tr>
        </thead>
        <tbody>
          {zeilen.map((k) => (
            <tr key={k.kategorie} className="border-b border-line text-14 text-ink">
              <th scope="row" className="py-2 pr-6 text-left font-sans font-normal">
                {k.kategorie}
              </th>
              <td className={zelle}>{formatZahl(k.basis)}</td>
              <td className={zelle}>{formatZahl(k.ziel)}</td>
              <td className={zelle}>{formatDifferenz(k.ziel - k.basis)}</td>
            </tr>
          ))}
          <tr className="text-14 font-semibold text-ink">
            <th scope="row" className="py-2 pr-6 text-left font-sans">
              Gesamt
            </th>
            <td className={zelle}>{formatZahl(e.basis.gesamt)}</td>
            <td className={zelle}>{formatZahl(e.ziel.gesamt)}</td>
            <td className={zelle}>{formatDifferenz(e.ziel.gesamt - e.basis.gesamt)}</td>
          </tr>
        </tbody>
      </table>
      </div>
      {e.auchImZiel.length > 0 && (
        <p className="font-sans text-14 text-slate">
          {`Der Stand „${regelsatzName(rz)}“ enthält auch ${e.auchImZiel.map((t) => `„${auftragKopf(`${t}:`).titel}“`).join(" und ")}. Der Unterschied kommt deshalb nicht nur aus diesem Auftrag.`}
        </p>
      )}
      <div>
        <BelegLink {...beleg} />
      </div>
    </DetailBlock>
  );
}
