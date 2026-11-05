import type { Metadata } from "next";
import Link from "next/link";
import { Fliesstext, knopfKlassen, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { formatZahl, formatZeit, HerkunftChip } from "@kic/ui/bausteine";
import { bestandBeleg } from "@/components/uc3/beleg";
import { leerSatz } from "@/components/uc3/db";
import { Fachbegriff } from "@/components/uc3/fachbegriff";
import { leseMonatsuebersicht, sqlRegelFreigaben } from "@/components/uc3/laeufe";
import { monatName } from "@/components/uc3/monat";
import { berichtPfad, laufPfad, regelsatzAus, uebersichtPfad, type Regelsatz } from "@/components/uc3/navigation";
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

/** Umschalter zwischen den Regelsätzen; erscheint erst, wenn es Läufe mit Regelsatz v2 gibt. */
function RegelsatzWahl({ aktiv }: { aktiv: Regelsatz }) {
  const punkte: Array<[Regelsatz, string]> = [
    ["v1", "Regelsatz v1, nach der Fachbeschreibung"],
    ["v2", "Regelsatz v2, mit den Änderungsaufträgen"],
  ];
  return (
    <nav aria-label="Regelsatz" className="flex flex-col gap-2">
      <Fachbegriff wort="Regelsatz" className="font-sans text-14 font-semibold text-ink" />
      <ul className="flex flex-wrap gap-x-6 gap-y-2">
        {punkte.map(([wert, text]) => (
          <li key={wert}>
            <Link
              href={uebersichtPfad(wert)}
              aria-current={wert === aktiv ? "page" : undefined}
              className={`font-sans text-14 underline-offset-4 ${wert === aktiv ? "font-semibold text-ink" : "text-gruen underline"}`}
            >
              {text}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

type Props = { searchParams: Promise<{ regelsatz?: string | string[] }> };

export default async function Monatslaeufe({ searchParams }: Props) {
  const regelsatz = regelsatzAus((await searchParams).regelsatz);
  const lesung = await leseMonatsuebersicht(regelsatz);

  if (!lesung.ok || lesung.daten.monate.length === 0) {
    const ohneV2 = lesung.ok && regelsatz === "v2";
    return (
      <>
        <Ueberschrift stufe={2} als="h1">
          {ohneV2 ? "Mit Regelsatz v2 ist noch kein Monat gerechnet." : "Noch kein Monat ist gerechnet."}
        </Ueberschrift>
        <Leerzustand
          satz={
            !lesung.ok
              ? leerSatz(lesung.grund)
              : ohneV2
                ? "Die Monate entstehen, sobald eine Änderung mit Namen freigegeben und gerechnet ist."
                : "Der erste Lauf beginnt mit August 2024."
          }
          aktion={
            ohneV2 ? (
              <Link href={uebersichtPfad("v1")} className={knopfKlassen("sekundaer")}>
                Monate mit Regelsatz v1 ansehen
              </Link>
            ) : undefined
          }
        />
      </>
    );
  }

  const { monate, regeln, regelsaetze } = lesung.daten;
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
            : `${ZAHLWORT[angehalten.length] ?? angehalten.length} davon ${angehalten.length === 1 ? "ist" : "sind"} angehalten und ${angehalten.length === 1 ? "wartet" : "warten"} auf die Antwort der Fachabteilung: ${aufzaehlen(angehalten.map((m) => monatName(m.lieferung)))}.`}
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
            <Link href={laufPfad(pruefen.lieferung, regelsatz)} className={knopfKlassen("primaer")}>
              {`${monatName(pruefen.lieferung)} prüfen`}
            </Link>
          ) : (
            <Link href={berichtPfad(letzter.lieferung, regelsatz)} className={knopfKlassen("primaer")}>
              {`Qualitätsbericht ${monatName(letzter.lieferung)} lesen`}
            </Link>
          )}
        </div>
        {(regelsaetze.includes("v2") || regelsatz === "v2") && <RegelsatzWahl aktiv={regelsatz} />}
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
        <Monatstabelle monate={monate} regelsatz={regelsatz} />
      </section>
    </>
  );
}

function letztes<T>(liste: readonly T[]): T {
  const element = liste.at(-1);
  if (element === undefined) throw new Error("leere Liste");
  return element;
}
