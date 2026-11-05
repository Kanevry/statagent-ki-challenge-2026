import type { Metadata } from "next";
import Link from "next/link";
import { Fliesstext, Leerzustand, Status, Ueberschrift } from "@kic/ui/basis";
import { formatZahl, HerkunftChip } from "@kic/ui/bausteine";
import { leseRegeln, REGEL_TYPEN, sqlRegeln, type Regel, type RegelTyp } from "@/components/uc3/bericht";
import { leerSatz } from "@/components/uc3/db";
import { Begriffsliste } from "@/components/uc3/fachbegriff";
import { monatName } from "@/components/uc3/monat";
import { alltag } from "@/components/uc3/sprache";

// Regeln des Regelsatzes v1 (#18, Frame egqhg): gruppiert nach Einlesen, Zuordnen, Zählen, Prüfen, mit
// Beschreibung, Begründung, Gültigkeit und Freigabe. Nur lesend; Freigaben laufen über die CLI.
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Regeln · StatAgent" };

const REGELSATZ = "v1";

const GRUPPEN: Record<RegelTyp, { name: string; satz: (n: number) => string }> = {
  einlese: { name: "Einlesen", satz: (n) => `${formatZahl(n)} Regeln legen fest, wie die Lieferung gelesen wird.` },
  zuordnung: { name: "Zuordnen", satz: (n) => `${formatZahl(n)} Regeln führen gelieferte Werte auf die offiziellen Codes.` },
  zaehl: { name: "Zählen", satz: (n) => `${formatZahl(n)} Regeln bestimmen, was am Stichtag als Beschäftigungsverhältnis zählt.` },
  pruefung: { name: "Prüfen", satz: (n) => `${formatZahl(n)} Regeln prüfen jeden Monat, ob etwas auffällt.` },
};

const link = "text-ink underline underline-offset-4 hover:text-gruen";

function gueltigkeit(r: Regel): string {
  return r.gueltigBis
    ? `gilt von ${monatName(r.gueltigAb)} bis ${monatName(r.gueltigBis)}`
    : `gilt ab der Lieferung ${monatName(r.gueltigAb)}`;
}

export default async function Regeln() {
  const lesung = await leseRegeln(REGELSATZ);

  if (!lesung.ok || lesung.daten.length === 0) {
    return (
      <>
        <Ueberschrift stufe={2} als="h1">
          Regeln
        </Ueberschrift>
        <Leerzustand satz={lesung.ok ? "Für den Regelsatz v1 ist noch keine Regel angelegt." : leerSatz(lesung.grund)} />
      </>
    );
  }

  const regeln = lesung.daten;
  const freigegeben = regeln.filter((r) => r.freigegebenVon).length;
  const freigabeText =
    freigegeben === 0
      ? "keine davon hat schon eine Freigabe mit Namen"
      : freigegeben === regeln.length
        ? "alle haben eine Freigabe mit Namen"
        : `${formatZahl(freigegeben)} davon ${freigegeben === 1 ? "hat" : "haben"} eine Freigabe mit Namen`;

  return (
    <>
      <header className="flex max-w-4xl flex-col gap-4">
        <Ueberschrift stufe={2} als="h1" className="hyphens-auto break-words">
          {`${formatZahl(regeln.length)} Regeln bestimmen, wie gelesen, zugeordnet, gezählt und geprüft wird, ${freigabeText}.`}
        </Ueberschrift>
        <HerkunftChip quelle="meta.regel" regelstand={`Regelsatz ${REGELSATZ}`} sql={sqlRegeln(REGELSATZ)} />
        <Fliesstext>
          Jede Regel steht als Datensatz in der Datenbank, nicht im Programmcode. Ändert sich eine Regel, ändert sich der
          Regelstand, und jeder Monat zeigt, mit welchem Regelstand er gerechnet wurde.
        </Fliesstext>
        <Fliesstext groesse={14}>
          <Link href="/uc3/berichte" className={link}>
            Zu den Qualitätsberichten
          </Link>
        </Fliesstext>
      </header>

      <Begriffsliste worte={["Regel", "Regelstand", "Freigabe"] as const} label="Begriffe auf dieser Seite" className="grid max-w-5xl gap-4 sm:grid-cols-3" />

      {REGEL_TYPEN.map((typ) => {
        const gruppe = regeln.filter((r) => r.typ === typ);
        if (gruppe.length === 0) return null;
        const id = `gruppe-${typ}`;
        return (
          <section key={typ} aria-labelledby={id} className="flex max-w-5xl flex-col gap-4 border-t border-line pt-8">
            <Fliesstext groesse={14} ton="gedaempft">
              {GRUPPEN[typ].name}
            </Fliesstext>
            <Ueberschrift stufe={3} als="h2" id={id}>
              {GRUPPEN[typ].satz(gruppe.length)}
            </Ueberschrift>
            <HerkunftChip quelle="meta.regel" regelstand={`Regelsatz ${REGELSATZ}`} sql={sqlRegeln(REGELSATZ)} />
            <ul className="flex flex-col">
              {gruppe.map((r) => (
                <li key={r.id} id={r.name} className="flex scroll-mt-24 flex-col gap-2 border-b border-line py-4 target:bg-paper" data-regel={r.name}>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <Fliesstext className="max-w-3xl">{alltag(r.beschreibung)}</Fliesstext>
                    <Status art={r.freigegebenVon ? "ok" : "warnung"}>
                      {r.freigegebenVon
                        ? `freigegeben von ${r.freigegebenVon} am ${r.freigegebenAm ?? ""}`
                        : "noch ohne Freigabe"}
                    </Status>
                  </div>
                  <Fliesstext groesse={14} ton="gedaempft" className="max-w-3xl">{`Begründung: ${alltag(r.begruendung)}`}</Fliesstext>
                  <p className="font-sans text-12 text-slate">
                    <span className="mr-2 break-all font-mono">{r.name}</span>
                    {gueltigkeit(r)}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </>
  );
}
