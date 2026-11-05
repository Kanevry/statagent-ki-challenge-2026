import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Fliesstext, Leerzustand, Status, Ueberschrift } from "@kic/ui/basis";
import { Begriff, HerkunftChip } from "@kic/ui/bausteine";
import { datum } from "@/components/uc3/bericht";
import { laufBeleg } from "@/components/uc3/beleg";
import { leerSatz } from "@/components/uc3/db";
import { Fachbegriff } from "@/components/uc3/fachbegriff";
import {
  leseKlassifikationen,
  qualifikationsZahlen,
  regelSatz,
  SQL_ALTERSGRUPPEN,
  SQL_BUNDESLAENDER,
  SQL_GESCHLECHT,
  SQL_QUALIFIKATION_ZAHLEN,
  SQL_QUALIFIKATIONEN,
  sqlAbschnittBestand,
  sqlAbschnitte,
  sqlUebergaenge,
  sqlWechselzahlen,
  sqlZuordnungsregel,
  uebergangsWorte,
  wechselSatz,
  wechselzahlen,
  zaehleUebergangsWorte,
  type Zuordnungsregel,
} from "@/components/uc3/klassifikation";
import { Abschnittstabelle } from "./_teile/abschnittstabelle";

// Klassifikationen (#18, Frame XlcSB): Branchen ÖNACE 2008 gegen 2025, wie gelieferte Codes zugeordnet werden und
// die kleinen Code-Listen. Liest die UC3-Datenbank; ohne Datenbank zeigt die Seite den Leerzustand (HTTP 200).
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Klassifikationen · StatAgent" };

const UMSTEIGESCHLUESSEL = "Eine Tabelle, die sagt, welcher alte Code zu welchem neuen Code gehört.";

function Freigabe({ regel }: { regel: Zuordnungsregel }) {
  if (!regel.freigegebenVon) return <Status art="warnung">noch ohne Freigabe</Status>;
  const am = regel.freigegebenAm ? ` am ${datum(regel.freigegebenAm)}` : "";
  return <Status art="ok">{`freigegeben von ${regel.freigegebenVon}${am}`}</Status>;
}

function Regelpunkt({ satz, name, status, children }: { satz: string; name?: string; status?: ReactNode; children: ReactNode }) {
  return (
    <li className="flex flex-col items-start gap-2 border-b border-line py-4">
      <p className="max-w-3xl font-sans text-16 text-ink">{satz}</p>
      {(name || status) && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {name && <span className="break-all font-mono text-12 text-slate">{`Regel ${name}`}</span>}
          {status}
        </div>
      )}
      {children}
    </li>
  );
}

function Liste({ satz, sql, quelle, children }: { satz: string; sql: string; quelle: string; children: ReactNode }) {
  return (
    <details className="border-b border-line py-3">
      <summary className="cursor-pointer font-sans text-16 text-ink underline-offset-4 hover:underline">{satz}</summary>
      <div className="mt-3 flex flex-col items-start gap-3">
        {children}
        <HerkunftChip quelle={quelle} sql={sql} />
      </div>
    </details>
  );
}

const codeZelle = "font-mono text-14 text-ink tabular-nums";

/** Häufigster Wert einer Liste, bei Gleichstand der zuerst gesehene; `null` bei leerer Liste. */
function haeufigster(werte: readonly string[]): string | null {
  const zaehlung = new Map<string, number>();
  for (const w of werte) zaehlung.set(w, (zaehlung.get(w) ?? 0) + 1);
  let bester: string | null = null;
  for (const [w, n] of zaehlung) if (bester === null || n > (zaehlung.get(bester) ?? 0)) bester = w;
  return bester;
}

export default async function Klassifikationen() {
  const lesung = await leseKlassifikationen();

  if (!lesung.ok || lesung.daten.abschnitte.length === 0) {
    return (
      <>
        <Ueberschrift stufe={2} als="h1">
          Klassifikationen
        </Ueberschrift>
        <Leerzustand
          satz={lesung.ok ? "Die Code-Listen sind noch nicht geladen. Sie kommen mit dem Startpaket in die Datenbank." : leerSatz(lesung.grund)}
        />
      </>
    );
  }

  const { abschnitte, uebergaenge, regeln, bestand, bundeslaender, geschlechter, qualifikationen, altersgruppen } =
    lesung.daten;
  const zahlen = wechselzahlen(abschnitte);
  const nameNeu = (code: string) => abschnitte.find((a) => a.code === code)?.neu?.bezeichnung;
  const umsteiger2025 = uebergaenge.filter((u) => u.versionNeu === "2025").length;
  const worte2003 = uebergangsWorte(uebergaenge.filter((u) => u.versionAlt === "2003" && u.versionNeu === "2008"));
  const zahl2003 = zaehleUebergangsWorte(worte2003);
  const aufgeteilt2003 = worte2003.filter((w) => w.wort === "aufgeteilt");
  // Ziel der zusammengelegten 2003er Codes aus stat.uebergang, nicht als Konstante (Review !51 Runde 2, Punkt 4).
  const ziel2003 = haeufigster(worte2003.filter((w) => w.wort === "zusammengelegt").flatMap((w) => w.ziele));
  const qZahlen = qualifikationsZahlen(qualifikationen);
  const kategorien = [...new Set(qualifikationen.map((q) => q.kategorie))];
  const ersteGruppe = altersgruppen[0];
  const bekannteGruppen = altersgruppen.filter((g) => g.von >= 0);

  return (
    <>
      <header className="flex max-w-4xl flex-col gap-4">
        <Ueberschrift stufe={2} als="h1" className="hyphens-auto break-words">
          {wechselSatz(zahlen)}
        </Ueberschrift>
        <HerkunftChip quelle="stat.klass_oenace" sql={sqlWechselzahlen()} />
        <Fliesstext>
          {`Bis Dezember 2024 gilt ÖNACE 2008. ${zahlen.verschoben} Abschnitte heißen gleich, tragen aber einen anderen Buchstaben, ${zahlen.neu} sind neu zugeschnitten. Wir vergleichen die Abschnitte über ihren Namen, nicht über den Buchstaben.`}
        </Fliesstext>
      </header>

      <ul className="grid max-w-5xl gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Begriffe auf dieser Seite">
        {(["Klassifikation", "ÖNACE", "Klassifikationswechsel", "Regel"] as const).map((wort) => (
          <li key={wort} className="font-sans text-14 font-semibold text-ink">
            <Fachbegriff wort={wort} />
          </li>
        ))}
        <li className="font-sans text-14 font-semibold text-ink">
          <Begriff wort="Umsteigeschlüssel" erklaerung={UMSTEIGESCHLUESSEL} untertitel />
        </li>
      </ul>

      <section aria-labelledby="wechsel-titel" className="flex flex-col gap-4">
        <Ueberschrift stufe={3} als="h2" id="wechsel-titel">
          Mit dem Klassifikationswechsel meint derselbe Buchstabe oft eine andere Branche.
        </Ueberschrift>
        <Fliesstext className="max-w-3xl">
          {umsteiger2025 === 0
            ? "In der Datenbank liegt noch kein Umsteigeschlüssel von ÖNACE 2008 auf 2025. Deshalb rechnen wir Branchenzahlen nicht um: Über den Jahreswechsel vergleichen wir nur die Summe, die Bundesländer und das Geschlecht."
            : "Über den Jahreswechsel vergleichen wir Branchen nur mit dem Umsteigeschlüssel. Die Summe, die Bundesländer und das Geschlecht bleiben direkt vergleichbar."}
        </Fliesstext>
        <div className="flex flex-wrap gap-2">
          <HerkunftChip quelle="stat.klass_oenace" sql={sqlAbschnitte()} />
          {bestand &&
            [bestand.alt, bestand.neu].map((lauf) => (
              <HerkunftChip key={lauf.lieferung} {...laufBeleg(lauf, { sql: sqlAbschnittBestand(bestand.alt, bestand.neu) })} />
            ))}
        </div>
        {bestand && (
          <Fliesstext groesse={14} ton="gedaempft">
            Die Zahlen sind Beschäftigungsverhältnisse am Stichtag, jeweils aus dem maßgeblichen Lauf des Monats. Je Monat nennt ein Beleg Lieferung, Regelstand und Lauf.
          </Fliesstext>
        )}
        <Abschnittstabelle zeilen={abschnitte} bestand={bestand?.werte ?? null} />
      </section>

      <section aria-labelledby="zuordnung-titel" className="flex flex-col gap-2">
        <Ueberschrift stufe={3} als="h2" id="zuordnung-titel">
          Jeden gelieferten Code ordnen wir nach einer Regel zu, auch leere und unbekannte.
        </Ueberschrift>
        <ul className="flex flex-col">
          {regeln.map((regel) => (
            <Regelpunkt key={regel.id} satz={regelSatz(regel, nameNeu)} name={regel.name} status={<Freigabe regel={regel} />}>
              <HerkunftChip quelle="stat.quellzuordnung" sql={sqlZuordnungsregel(regel.id)} />
              {regel.zuordnungen.some((z) => z.geliefert.startsWith("D") && z.geliefert.length === 2) &&
                worte2003.length > 0 && (
                  <>
                    <Fliesstext groesse={14} ton="gedaempft" className="max-w-3xl">
                      {`Laut Umsteigeschlüssel von ÖNACE 2003 auf 2008 gehen ${zahl2003.zusammengelegt} dieser Codes ganz in ${ziel2003 ?? "einen Abschnitt"} auf.${
                        aufgeteilt2003.length > 0
                          ? ` ${aufgeteilt2003.map((w) => `${w.codeAlt} ist auf ${w.ziele.join(" und ")} aufgeteilt`).join(", ")}. Wir zählen ${aufgeteilt2003.length === 1 ? "ihn" : "sie"} nach der Zuordnungsregel unter ${haeufigster(regel.zuordnungen.filter((z) => z.geliefert.startsWith("D") && z.geliefert.length === 2).map((z) => z.code)) ?? "dem zugeordneten Abschnitt"}.`
                          : ""
                      }`}
                    </Fliesstext>
                    <HerkunftChip quelle="stat.uebergang" sql={sqlUebergaenge()} />
                  </>
                )}
            </Regelpunkt>
          ))}
          <Regelpunkt
            satz={`Die ${qZahlen.qualifikationen} gelieferten Qualifikationen fassen wir zu ${qZahlen.kategorien} Beschäftigungskategorien zusammen. Ein freier Dienstvertrag zählt zu seiner Kategorie.`}
            status={
              <span className="font-sans text-12 text-slate">So steht es in der Liste der Qualifikationen.</span>
            }
          >
            <HerkunftChip quelle="stat.klass_qualifikation" sql={SQL_QUALIFIKATION_ZAHLEN} />
          </Regelpunkt>
        </ul>
      </section>

      <section aria-labelledby="listen-titel" className="flex max-w-3xl flex-col gap-2">
        <Ueberschrift stufe={3} als="h2" id="listen-titel">
          Die übrigen Listen ändern sich im Berichtszeitraum nicht.
        </Ueberschrift>

        <Liste
          satz={`${bundeslaender.length} Codes für das Bundesland, davon einer für unbekannt.`}
          sql={SQL_BUNDESLAENDER}
          quelle="stat.klass_region"
        >
          <ul className="grid w-full grid-cols-1 gap-x-8 gap-y-1 sm:grid-cols-2">
            {bundeslaender.map((b) => (
              <li key={b.code} className="flex gap-3 font-sans text-14 text-ink">
                <span className={`${codeZelle} w-6 text-right`}>{b.code}</span>
                <span>{b.bezeichnung}</span>
              </li>
            ))}
          </ul>
        </Liste>

        <Liste
          satz={`${geschlechter.length} Codes für das Geschlecht, davon einer für unbekannt.`}
          sql={SQL_GESCHLECHT}
          quelle="stat.klass_geschlecht"
        >
          <ul className="flex flex-col gap-1">
            {geschlechter.map((g) => (
              <li key={g.code} className="flex gap-3 font-sans text-14 text-ink">
                <span className={`${codeZelle} w-6`}>{g.code}</span>
                <span>{g.bezeichnung}</span>
              </li>
            ))}
          </ul>
        </Liste>

        <Liste
          satz={`${qualifikationen.length} Qualifikationen in ${kategorien.length} Beschäftigungskategorien, jeweils mit einem Code für unbekannt.`}
          sql={SQL_QUALIFIKATIONEN}
          quelle="stat.klass_qualifikation"
        >
          <ul className="flex w-full flex-col">
            {qualifikationen.map((q) => (
              <li key={q.code} className="flex flex-col border-b border-line py-2 last:border-b-0 sm:flex-row sm:gap-4">
                <span className={`${codeZelle} sm:w-36 sm:shrink-0`}>{q.code}</span>
                <span className="font-sans text-14 text-ink sm:flex-1">{q.bezeichnung}</span>
                <span className="font-sans text-14 text-slate">{`Kategorie: ${q.kategorie}`}</span>
              </li>
            ))}
          </ul>
        </Liste>

        <Liste
          satz={`${altersgruppen.length} Altersgruppen für den Bericht, von „${bekannteGruppen[0]?.gruppe ?? ""}“ bis „${bekannteGruppen.at(-1)?.gruppe ?? ""}“${ersteGruppe && ersteGruppe.von < 0 ? ", dazu unbekannt" : ""}.`}
          sql={SQL_ALTERSGRUPPEN}
          quelle="stat.klass_alter"
        >
          <ul className="flex flex-wrap gap-x-4 gap-y-1">
            {altersgruppen.map((g) => (
              <li key={g.gruppe} className="font-sans text-14 text-ink">
                {g.gruppe}
                {g.von >= 0 && g.von !== g.bis && (
                  <span className="font-mono text-12 tabular-nums text-slate">{` (${g.von} bis ${g.bis} Jahre)`}</span>
                )}
              </li>
            ))}
          </ul>
        </Liste>
      </section>
    </>
  );
}
