import type { Metadata } from "next";
import { Fliesstext, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { formatZahl } from "@kic/ui/bausteine";
import { BelegLink, StandPunkt } from "@/components/uc3/beleg-link";
import { DatenFehler } from "@/components/uc3/daten-fehler";
import { standName } from "@/components/uc3/klassifikation-tief";
import {
  lesePensionen,
  SQL_LADUNG,
  SQL_PENSIONEN,
  SQL_TABELLEN,
  SQL_TRAEGER,
  SQL_ZUSAMMENLEGUNG,
  type Pensionsdaten,
  type PensionsTabelle,
} from "@/components/uc3/pensionen";

// Pensionen je Träger (Raster Bereich 1, #77): die Tabellen 12 und 13 aus stat.stat_pensionen, der Wechsel der Träger 2020
// aus stat.uebergang und was fehlt. Nur lesend; was die Datenbank nicht trägt, steht hier nicht. Ohne Tabelle ein
// Leerzustand mit HTTP 200.
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Pensionen · StatAgent" };

const titel = "font-sans text-16 font-semibold text-ink";
const EINRUECKEN: Record<number, string> = { 3: "pl-3", 4: "pl-6" };

function Tabelle({ tabelle, jahre, bruch }: { tabelle: PensionsTabelle; jahre: readonly number[]; bruch: number | null }) {
  return (
    <div
      role="region"
      aria-label={`${tabelle.titel}, zum Verschieben`}
      tabIndex={0}
      // relative: Die sr-only-Texte sind absolut positioniert und schöben sonst die ganze Seite breiter als den Bildschirm.
      className="relative w-full overflow-x-auto focus-visible:outline-2 focus-visible:outline-offset-2"
    >
      <table className="w-full border-collapse font-sans text-14 text-ink">
        <caption className="sr-only">{`${tabelle.titel}, Durchschnitt je Jahr und Träger`}</caption>
        <thead>
          <tr className="border-b border-ink text-slate">
            <th scope="col" className="sticky left-0 bg-paper py-2 pr-3 text-left font-normal">
              Träger
            </th>
            {jahre.map((j) => (
              <th key={j} scope="col" className={`p-2 text-right font-normal tabular-nums ${j === bruch ? "border-l border-line" : ""}`}>
                {j}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tabelle.zeilen.map((z) => (
            <tr key={z.code} className="border-b border-line">
              <th
                scope="row"
                className={`sticky left-0 min-w-40 bg-paper py-2 pr-3 text-left sm:min-w-72 ${z.ebene <= 2 ? "font-semibold" : "font-normal"} ${EINRUECKEN[z.ebene] ?? ""}`}
              >
                {z.name}
              </th>
              {z.werte.map((wert, i) => (
                <td
                  key={jahre[i]}
                  className={`p-2 text-right tabular-nums ${z.ebene <= 2 ? "font-semibold" : ""} ${jahre[i] === bruch ? "border-l border-line" : ""}`}
                >
                  {wert === null ? <span className="sr-only">keine Meldung</span> : formatZahl(wert)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Kopf({ daten }: { daten: Pensionsdaten }) {
  const insgesamt = daten.tabellen[0]?.zeilen[0]?.werte.at(-1) ?? null;
  const jahr = daten.jahre.at(-1);
  return (
    <header className="flex max-w-4xl flex-col gap-3">
      <Ueberschrift stufe={2} als="h1" className="hyphens-auto break-words">
        {insgesamt === null
          ? "Pensionen je Träger"
          : `${jahr} melden die Träger im Schnitt ${formatZahl(insgesamt)} Pensionen. Hier steht jeder meldende Träger je Jahr seit ${daten.jahre[0]}.`}
      </Ueberschrift>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {daten.vorlaeufig ? (
          <StandPunkt stand="vorlaeufig" wort="vorläufig, noch nicht mit Namen freigegeben" />
        ) : (
          <StandPunkt
            stand="freigegeben"
            wort={daten.freigabe ? `Freigegeben von ${daten.freigabe.name}${daten.freigabe.am ? ` am ${standName(daten.freigabe.am)}` : ""}` : undefined}
          />
        )}
        <BelegLink
          quelle="stat.stat_pensionen, stat.klass_versicherungstraeger, stat.klass_pensionsart"
          sql={`${SQL_PENSIONEN};\n\n${SQL_TRAEGER};\n\n${SQL_TABELLEN};`}
        />
      </div>
    </header>
  );
}

export default async function PensionenSeite() {
  const lesung = await lesePensionen();
  if (!lesung.ok) return <DatenFehler grund={lesung.grund} />;
  const daten = lesung.daten;
  if (daten.tabellen.length === 0) {
    return (
      <header className="flex max-w-4xl flex-col gap-3">
        <Ueberschrift stufe={2} als="h1">
          Pensionen je Träger
        </Ueberschrift>
        <Leerzustand satz="Die Pensionen sind in dieser Datenbank noch nicht geladen." />
      </header>
    );
  }
  const [stand, ...weitere] = daten.tabellen;
  return (
    <>
      <Kopf daten={daten} />

      {daten.zusammenlegung && (
        <div className="flex max-w-4xl flex-wrap items-baseline gap-x-3 gap-y-1">
          <Fliesstext>{daten.zusammenlegung}</Fliesstext>
          <BelegLink quelle="stat.uebergang" sql={SQL_ZUSAMMENLEGUNG} />
        </div>
      )}

      {stand && (
        <section aria-labelledby={`tabelle-${stand.code}`} className="flex w-full max-w-5xl min-w-0 flex-col gap-2">
          <h2 id={`tabelle-${stand.code}`} className={titel}>
            {stand.titel}
          </h2>
          <Tabelle tabelle={stand} jahre={daten.jahre} bruch={daten.bruchJahr} />
          <p className="max-w-3xl font-sans text-14 text-slate">
            Arbeiter und Angestellte sind hier Versicherungsbereiche der PVA, nicht die Qualifikationen aus der
            Beschäftigtenstatistik.
          </p>
        </section>
      )}

      {daten.fehlt.length > 0 && (
        <section aria-labelledby="fehlt-titel" className="flex max-w-3xl flex-col gap-2">
          <h2 id="fehlt-titel" className={titel}>
            Was fehlt
          </h2>
          {daten.fehlt.map((satz) => (
            <Fliesstext key={satz}>{satz}</Fliesstext>
          ))}
        </section>
      )}

      {weitere.map((t) => (
        <section key={t.code} aria-labelledby={`tabelle-${t.code}`} className="flex w-full max-w-5xl min-w-0 flex-col gap-2">
          <h2 id={`tabelle-${t.code}`} className={titel}>
            {t.titel}
          </h2>
          <p className="max-w-3xl font-sans text-14 text-slate">Sie sind ein Teil der Alterspensionen und zählen nicht zusätzlich.</p>
          <Tabelle tabelle={t} jahre={daten.jahre} bruch={daten.bruchJahr} />
        </section>
      ))}

      {daten.pruefung && (
        <div className="flex max-w-4xl flex-wrap items-baseline gap-x-3 gap-y-1">
          <Fliesstext ton="gedaempft">{daten.pruefung}</Fliesstext>
          <BelegLink quelle="meta.pension_ladung, meta.pension_summe" sql={SQL_LADUNG} />
        </div>
      )}
    </>
  );
}
