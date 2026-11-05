import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Fliesstext, knopfKlassen, Leerzustand, Status, Ueberschrift } from "@kic/ui/basis";
import { formatZahl, HerkunftChip } from "@kic/ui/bausteine";
import { abrechnungBeleg, laufBeleg } from "@/components/uc3/beleg";
import { leerSatz } from "@/components/uc3/db";
import { Fachbegriff } from "@/components/uc3/fachbegriff";
import { abrechnung } from "@/components/uc3/laeufe";
import {
  abrechnungSatz,
  bestandSatz,
  bleibtVorlaeufigSatz,
  determinismusSatz,
  haltSatz,
  haltTreffer,
  hatRevisionsbedarf,
  kannVeroeffentlichen,
  leseLaufDetail,
  regelsatzAus,
  revisionSatz,
  sqlBestandMitVormonat,
  sqlDeterminismus,
  sqlKeineRevision,
  sqlKennzahlen,
  sqlRegionen,
  sqlRevision,
  sqlTreffer,
  sqlVeroeffentlichen,
  umschichtungSatz,
  ursachenSatz,
  type LaufDetail,
} from "@/components/uc3/lauf-detail";
import { istMonat, monatName, stichtag, verschieben } from "@/components/uc3/monat";
import { berichtPfad, laufPfad } from "@/components/uc3/navigation";
import type { Lauf } from "@/components/uc3/typen";
import { Auffaelligkeiten } from "./_teile/auffaelligkeiten";
import { Bundeslaender } from "./_teile/bundeslaender";

// Lauf-Detail (#18, Frames fFDc8 und P6gBQD): ein Monat mit Bestand, Abrechnung, Auffälligkeiten, Revisionsbedarf
// und Bundesländern. Alles kommt aus einer Lesung; ohne Datenbank zeigt die Seite den Leerzustand (HTTP 200).
export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ lieferung: string }>;
  searchParams: Promise<{ regelsatz?: string | string[] }>;
};

/** Pfad eines Monats; mit Regelsatz v2 bleibt der Parameter erhalten. */
function monatsPfad(lieferung: string, regelsatz: string): string {
  return regelsatz === "v2" ? `${laufPfad(lieferung)}?regelsatz=v2` : laufPfad(lieferung);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { lieferung } = await params;
  return { title: istMonat(lieferung) ? `${monatName(lieferung)} · StatAgent` : "Monatslauf · StatAgent" };
}

const link = "font-sans text-14 text-ink underline underline-offset-4 hover:text-gruen";

function LaufStatus({ lauf, angehalten }: { lauf: Lauf; angehalten: boolean }) {
  if (!abrechnung(lauf).gehtAuf) return <Status art="fehler">Abrechnung geht nicht auf</Status>;
  if (angehalten) return <Status art="warnung">angehalten, vorläufig</Status>;
  if (lauf.ergebnisStand === "endgueltig") return <Status art="ok">veröffentlicht</Status>;
  return <Status art="info">vorläufig</Status>;
}

function Kennzahl({ wort, wert, zusatz }: { wort: string; wert: number; zusatz?: string }) {
  return (
    <div className="flex flex-col gap-1 border-t border-line pt-2">
      <dt className="font-sans text-14 text-slate">{wort}</dt>
      <dd className="font-mono text-32 tabular-nums text-ink">{formatZahl(wert)}</dd>
      {zusatz && <dd className="font-sans text-12 text-slate">{zusatz}</dd>}
    </div>
  );
}

function Weiter({ lieferung, regelsatz, davor, danach }: { lieferung: string; regelsatz: string; davor: boolean; danach: boolean }) {
  const vor = verschieben(lieferung, -1);
  const nach = verschieben(lieferung, 1);
  return (
    <nav aria-label="Weitere Monate" className="flex flex-col gap-4 border-t border-line pt-6">
      <div>
        <Link href={berichtPfad(lieferung)} className={knopfKlassen("primaer")}>
          {`Qualitätsbericht ${monatName(lieferung)} lesen`}
        </Link>
      </div>
      <ul className="flex flex-wrap gap-x-6 gap-y-2">
        {davor && (
          <li>
            <Link href={monatsPfad(vor, regelsatz)} className={link}>{`Vormonat: ${monatName(vor)}`}</Link>
          </li>
        )}
        {danach && (
          <li>
            <Link href={monatsPfad(nach, regelsatz)} className={link}>{`Nächster Monat: ${monatName(nach)}`}</Link>
          </li>
        )}
        <li>
          <Link href="/uc3" className={link}>
            Alle Monatsläufe
          </Link>
        </li>
      </ul>
    </nav>
  );
}

export default async function LaufSeite({ params, searchParams }: Props) {
  const { lieferung } = await params;
  if (!istMonat(lieferung)) notFound();
  const regelsatz = regelsatzAus((await searchParams).regelsatz);

  const lesung = await leseLaufDetail(lieferung, regelsatz);
  if (!lesung.ok || lesung.daten === null) {
    const name = monatName(lieferung);
    const satz = !lesung.ok
      ? leerSatz(lesung.grund)
      : regelsatz === "v2"
        ? `Für ${name} gibt es mit Regelsatz v2 noch keinen Lauf. Er entsteht, sobald die freigegebene Änderung gerechnet ist.`
        : `Für ${name} gibt es noch keinen Lauf.`;
    return (
      <>
        <Ueberschrift stufe={2} als="h1" className="hyphens-auto break-words">
          {name}
        </Ueberschrift>
        {regelsatz === "v2" && (
          <p className="font-sans text-14 font-semibold text-ink">
            <Fachbegriff wort="Regelsatz" />
          </p>
        )}
        <Leerzustand
          satz={satz}
          aktion={
            <ul className="flex flex-wrap gap-x-6 gap-y-2">
              {regelsatz === "v2" && lesung.ok && (
                <li>
                  <Link href={laufPfad(lieferung)} className={link}>{`${name} mit Regelsatz v1`}</Link>
                </li>
              )}
              <li>
                <Link href="/uc3" className={link}>
                  Alle Monatsläufe
                </Link>
              </li>
            </ul>
          }
        />
      </>
    );
  }

  return <Detail detail={lesung.daten} />;
}

/** Wie es mit einem vorläufigen Monat weitergeht; den Befehl gibt es nur, wenn die CLI ihn auch ausführt. */
function SoGehtEsWeiter({ detail, angehalten }: { detail: LaufDetail; angehalten: boolean }) {
  const { lauf, veroeffentlichen } = detail;
  if (lauf.ergebnisStand === "endgueltig") return null;
  const name = monatName(lauf.lieferung);
  const kann = kannVeroeffentlichen(lauf, angehalten, veroeffentlichen);
  const wartet = angehalten || lauf.fortgeschrieben > 0;
  const befehl = `uv run uc3 veroeffentlichen --lieferung ${lauf.lieferung}${lauf.regelsatz === "v1" ? "" : ` --regelsatz ${lauf.regelsatz}`} --name "Vorname Nachname"`;
  return (
    <section
      aria-labelledby="weiter-titel"
      className={`flex max-w-3xl flex-col items-start gap-2 border-l-2 pl-4 ${wartet ? "border-warn-fg" : "border-line"}`}
    >
      <Ueberschrift stufe={3} als="h2" id="weiter-titel">
        {`So geht es mit ${name} weiter.`}
      </Ueberschrift>
      {kann ? (
        <>
          <Fliesstext>
            Alle Regeln und der Regelstand sind mit Namen freigegeben, keine Prüfung hält den Monat an. Diese Seite
            ändert nichts; veröffentlicht wird mit diesem Befehl:
          </Fliesstext>
          <code className="block w-full overflow-x-auto break-all bg-paper py-2 font-mono text-14 text-ink">{befehl}</code>
        </>
      ) : wartet ? (
        <Fliesstext>{bleibtVorlaeufigSatz(veroeffentlichen.wartetAuf)}</Fliesstext>
      ) : (
        <Fliesstext>
          {veroeffentlichen.regelnOhneFreigabe > 0
            ? `Der Monat bleibt vorläufig, bis ${veroeffentlichen.regelnOhneFreigabe === 1 ? "die letzte Regel" : `${formatZahl(veroeffentlichen.regelnOhneFreigabe)} Regeln`} mit Namen freigegeben ${veroeffentlichen.regelnOhneFreigabe === 1 ? "ist" : "sind"}.`
            : "Der Monat bleibt vorläufig, bis der Regelstand für diesen Monat mit Namen freigegeben ist."}
        </Fliesstext>
      )}
      <HerkunftChip {...laufBeleg(lauf, { quelle: "meta.regel", sql: sqlVeroeffentlichen(lauf) })} />
    </section>
  );
}

function Detail({ detail }: { detail: LaufDetail }) {
  const { lauf, vormonat, treffer, revisionen, regionen, determinismus } = detail;
  const halt = haltTreffer(treffer);
  const name = monatName(lauf.lieferung);
  const tag = stichtag(lauf.lieferung);
  const bestandChip = laufBeleg(lauf, { quelle: "stat.stat_beschaeftigte", sql: sqlBestandMitVormonat(lauf, vormonat) });
  const kennzahlChip = laufBeleg(lauf, { quelle: "meta.lauf", sql: sqlKennzahlen(lauf) });
  const mitRevision = revisionen.filter(hatRevisionsbedarf);

  return (
    <>
      <header className="flex max-w-4xl flex-col gap-4">
        <Fliesstext groesse={14} ton="gedaempft">
          {`Monatslauf ${name}, Stichtag ${tag}${lauf.regelsatz === "v1" ? "" : `, gerechnet mit Regelsatz ${lauf.regelsatz}`}`}
        </Fliesstext>
        <Ueberschrift stufe={2} als="h1" className="hyphens-auto break-words">
          {halt ? haltSatz(halt, lauf.lieferung) : bestandSatz(lauf, vormonat)}
        </Ueberschrift>
        {halt ? (
          <HerkunftChip {...laufBeleg(lauf, { quelle: "meta.pruefung_treffer", sql: sqlTreffer(lauf, halt) })} />
        ) : (
          <HerkunftChip {...bestandChip} />
        )}
        <div className="flex flex-wrap items-center gap-4">
          <LaufStatus lauf={lauf} angehalten={halt !== null} />
          <Fliesstext groesse={14} ton="gedaempft">
            {lauf.ergebnisStand === "endgueltig" && lauf.freigegebenVon
              ? `Veröffentlicht von ${lauf.freigegebenVon}.`
              : "Noch nicht veröffentlicht."}
          </Fliesstext>
        </div>
        {lauf.regelsatz !== "v1" && (
          <p className="font-sans text-14 font-semibold text-ink">
            <Fachbegriff wort="Regelsatz" />
          </p>
        )}
      </header>

      <SoGehtEsWeiter detail={detail} angehalten={halt !== null} />

      <section aria-labelledby="zahlen-titel" className="flex max-w-4xl flex-col gap-4">
        <Ueberschrift stufe={3} als="h2" id="zahlen-titel">
          Jeder gelesene Satz ist gezählt, nicht gezählt oder ausgeschlossen.
        </Ueberschrift>
        <ul className="grid gap-4 sm:grid-cols-2" aria-label="Begriffe in diesem Abschnitt">
          {(lauf.fortgeschrieben > 0
            ? (["Abrechnung", "Sätze", "fortgeschrieben", "vorläufig"] as const)
            : (["Abrechnung", "Sätze", "vorläufig"] as const)).map((wort) => (
            <li key={wort} className="font-sans text-14 font-semibold text-ink">
              <Fachbegriff wort={wort} />
            </li>
          ))}
        </ul>
        {halt && (
          <div className="flex flex-col items-start gap-2">
            <Fliesstext>{bestandSatz(lauf, vormonat)}</Fliesstext>
            <HerkunftChip {...bestandChip} />
          </div>
        )}
        <dl className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Kennzahl wort="gelesen" wert={lauf.gelesen} />
          <Kennzahl
            wort="gezählt am Stichtag"
            wert={lauf.gezaehlt}
            zusatz={lauf.fortgeschrieben > 0 ? `davon ${formatZahl(lauf.fortgeschrieben)} aus dem Vormonat übernommen` : undefined}
          />
          <Kennzahl wort="nicht gezählt" wert={lauf.nichtGezaehlt} />
          <Kennzahl wort="ausgeschlossen" wert={lauf.ausgeschlossen} />
        </dl>
        <HerkunftChip {...kennzahlChip} />
        <div className="flex flex-col items-start gap-2">
          <Fliesstext>{abrechnungSatz(lauf)}</Fliesstext>
          <HerkunftChip {...abrechnungBeleg(lauf)} />
        </div>
        <div className="flex flex-col items-start gap-2">
          <Fliesstext groesse={14}>{`Dieselben Daten und Regeln ergeben dieselben Zahlen: ${determinismusSatz(determinismus)}`}</Fliesstext>
          <p className="font-sans text-14 font-semibold text-ink">
            <Fachbegriff wort="Ergebnis-Hash" />
          </p>
          <HerkunftChip {...laufBeleg(lauf, { quelle: "meta.lauf", sql: sqlDeterminismus(lauf) })} />
        </div>
      </section>

      <section aria-labelledby="auffaellig-titel" className="flex max-w-4xl flex-col gap-4">
        <Ueberschrift stufe={3} als="h2" id="auffaellig-titel">
          {treffer.length === 0
            ? "In diesem Monat ist keine Prüfung auffällig."
            : `In diesem Monat ${treffer.length === 1 ? "ist eine Prüfung" : `sind ${formatZahl(treffer.length)} Prüfungen`} auffällig.`}
        </Ueberschrift>
        <ul className="grid gap-4 sm:grid-cols-2" aria-label="Begriffe in diesem Abschnitt">
          {(["Auffälligkeit", "Einstufung"] as const).map((wort) => (
            <li key={wort} className="font-sans text-14 font-semibold text-ink">
              <Fachbegriff wort={wort} />
            </li>
          ))}
        </ul>
        {treffer.length > 0 && <Auffaelligkeiten lauf={lauf} treffer={treffer} />}
      </section>

      <section aria-labelledby="revision-titel" className="flex max-w-4xl flex-col gap-4">
        <Ueberschrift stufe={3} als="h2" id="revision-titel">
          {mitRevision.length === 0
            ? "Diese Lieferung ändert keinen früheren Monat."
            : `Diese Lieferung zeigt Revisionsbedarf für ${mitRevision.length === 1 ? "einen früheren Monat" : `${formatZahl(mitRevision.length)} frühere Monate`}.`}
        </Ueberschrift>
        <p className="font-sans text-14 font-semibold text-ink">
          <Fachbegriff wort="Revisionsbedarf" />
        </p>
        {mitRevision.length === 0 ? (
          <HerkunftChip {...laufBeleg(lauf, { quelle: "meta.revision", sql: sqlKeineRevision(lauf) })} />
        ) : (
          <ul className="flex flex-col" aria-label="Revisionsbedarf je Monat">
            {mitRevision.map((r) => {
              const gruende = ursachenSatz(r.ursachen);
              return (
                <li key={r.berichtsmonat} className="flex flex-col items-start gap-2 border-b border-line py-4">
                  <Fliesstext>{r.differenz === 0 ? umschichtungSatz(r) : revisionSatz(r)}</Fliesstext>
                  {gruende && <Fliesstext groesse={14} ton="gedaempft">{gruende}</Fliesstext>}
                  <HerkunftChip
                    {...laufBeleg(lauf, { quelle: "meta.revision", monat: r.berichtsmonat, sql: sqlRevision(lauf, r.berichtsmonat) })}
                  />
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section aria-labelledby="land-titel" className="flex max-w-4xl flex-col gap-4">
        <Ueberschrift stufe={3} als="h2" id="land-titel">
          {`So verteilen sich die Verhältnisse am ${tag} auf die Bundesländer.`}
        </Ueberschrift>
        {regionen.length === 0 ? (
          <Leerzustand satz={`Für ${name} liegen keine Zahlen je Bundesland vor.`} />
        ) : (
          <Bundeslaender regionen={regionen} stichtag={tag} />
        )}
        <HerkunftChip {...laufBeleg(lauf, { sql: sqlRegionen(lauf) })} />
      </section>

      <Weiter lieferung={lauf.lieferung} regelsatz={lauf.regelsatz} davor={detail.davor} danach={detail.danach} />
    </>
  );
}
