import type { Metadata } from "next";
import Link from "next/link";
import { Fliesstext, knopfKlassen, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { formatZahl, formatZeit, HerkunftChip } from "@kic/ui/bausteine";
import { bestandBeleg } from "@/lib/uc3/beleg";
import { leerSatz } from "@/lib/uc3/db";
import { Fachbegriff } from "@/lib/uc3/fachbegriff";
import { leseMonatsuebersicht, sqlRegelFreigaben } from "@/lib/uc3/laeufe";
import { monatName } from "@/lib/uc3/monat";
import { berichtPfad, laufPfad } from "@/lib/uc3/navigation";
import { gemeinsamerRegelstand, Monatstabelle } from "./_teile/monatstabelle";

// Monatsläufe (#18, Frames bgAUw und iU5QZ): eine Zeile je Berichtsmonat mit dem maßgeblichen Lauf. Liest die
// UC3-Datenbank direkt; ohne Datenbank zeigt die Seite den Leerzustand (HTTP 200, auch in CI).
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Monatsläufe · StatAgent" };

function aufzaehlen(teile: readonly string[]): string {
  return teile.length < 2 ? (teile[0] ?? "") : `${teile.slice(0, -1).join(", ")} und ${teile.at(-1)}`;
}

/** Zahlwort vor „davon“: „Einer davon ist angehalten“, „Zwei davon sind angehalten“. */
const ZAHLWORT = ["Keiner", "Einer", "Zwei", "Drei", "Vier", "Fünf"];

export default async function Monatslaeufe() {
  const lesung = await leseMonatsuebersicht();

  if (!lesung.ok || lesung.daten.monate.length === 0) {
    return (
      <>
        <Ueberschrift stufe={2} als="h1">
          Monatsläufe
        </Ueberschrift>
        <Leerzustand
          satz={
            lesung.ok
              ? "Noch kein Monat ist gerechnet. Der erste Lauf beginnt mit August 2024."
              : leerSatz(lesung.grund)
          }
        />
      </>
    );
  }

  const { monate, regeln } = lesung.daten;
  const erster = monate[0];
  const letzter = letztes(monate);
  const angehalten = monate.filter((m) => m.angehalten);
  const alleVorlaeufig = monate.every((m) => m.ergebnisStand === "vorlaeufig");
  const pruefen = angehalten.at(-1);
  const regelstand = gemeinsamerRegelstand(monate);

  return (
    <>
      <header className="flex max-w-4xl flex-col gap-4">
        <Ueberschrift stufe={2} als="h1" className="hyphens-auto break-words">
          {`Ende ${monatName(letzter.lieferung)} gab es ${formatZahl(letzter.gezaehlt)} Beschäftigungsverhältnisse.`}
        </Ueberschrift>
        <HerkunftChip {...bestandBeleg(letzter)} />
        <Fliesstext ton="gedaempft">
          Ein Programm prüft und zählt die Beschäftigtenstatistik. KI-Helfer schlagen Regeln vor, ein Mensch gibt sie frei.
        </Fliesstext>
        <Fliesstext>
          {`${monate.length} Monate von ${monatName(erster.lieferung)} bis ${monatName(letzter.lieferung)} sind gerechnet. `}
          {angehalten.length === 0
            ? "Kein Monat ist angehalten."
            : `${ZAHLWORT[angehalten.length] ?? angehalten.length} davon ${angehalten.length === 1 ? "ist" : "sind"} angehalten und ${angehalten.length === 1 ? "braucht" : "brauchen"} Ihr Urteil: ${aufzaehlen(angehalten.map((m) => monatName(m.lieferung)))}.`}
        </Fliesstext>
        {alleVorlaeufig && regeln.ohneFreigabe > 0 && (
          <div className="flex flex-col items-start gap-2">
            <Fliesstext groesse={14} ton="gedaempft">
              {`Alle Zahlen sind vorläufig, weil ${formatZahl(regeln.ohneFreigabe)} von ${formatZahl(regeln.aktiv)} Regeln noch keine Freigabe mit Namen haben.`}
            </Fliesstext>
            <HerkunftChip quelle="meta.regel" sql={sqlRegelFreigaben()} />
          </div>
        )}
        <Fliesstext groesse={14} ton="gedaempft">
          {`Datenstand: Lieferung ${monatName(letzter.lieferung)}, gerechnet am ${formatZeit(letzter.gestartetAm)}.`}
        </Fliesstext>
        <div>
          {pruefen ? (
            <Link href={laufPfad(pruefen.lieferung)} className={knopfKlassen("primaer")}>
              {`${monatName(pruefen.lieferung)} prüfen`}
            </Link>
          ) : (
            <Link href={berichtPfad(letzter.lieferung)} className={knopfKlassen("primaer")}>
              {`Qualitätsbericht ${monatName(letzter.lieferung)} lesen`}
            </Link>
          )}
        </div>
      </header>

      <ul className="grid max-w-5xl gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Begriffe auf dieser Seite">
        {(["Stichtag", "Beschäftigungsverhältnis", "Abrechnung", "Sätze", "vorläufig"] as const).map((wort) => (
          <li key={wort} className="font-sans text-14 font-semibold text-ink">
            <Fachbegriff wort={wort} />
          </li>
        ))}
      </ul>

      <section aria-labelledby="monate-titel" className="flex flex-col gap-4">
        <Ueberschrift stufe={3} als="h2" id="monate-titel">
          Jeder Monat wird aus seiner eigenen Lieferung gerechnet, jeder gelesene Satz ist abgerechnet.
        </Ueberschrift>
        {regelstand && (
          <Fliesstext groesse={14} ton="gedaempft">
            {`Alle Monate sind mit demselben Regelstand ${regelstand} gerechnet.`}
          </Fliesstext>
        )}
        <Monatstabelle monate={monate} />
      </section>
    </>
  );
}

function letztes<T>(liste: readonly T[]): T {
  const element = liste.at(-1);
  if (element === undefined) throw new Error("leere Liste");
  return element;
}
