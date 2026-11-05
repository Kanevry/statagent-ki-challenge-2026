import type { Metadata } from "next";
import Link from "next/link";
import { knopfKlassen, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { formatZahl } from "@kic/ui/bausteine";
import { bestandBeleg, laufBeleg, literal } from "@/components/uc3/beleg";
import { BelegLink } from "@/components/uc3/beleg-link";
import { DatenFehler } from "@/components/uc3/daten-fehler";
import { abrechnung, leseMonatsuebersicht, MASSGEBLICH_SQL } from "@/components/uc3/laeufe";
import { haltKurz, haltTreffer, leseLaufDetail, sqlTreffer } from "@/components/uc3/lauf-detail";
import { monatName, verschieben } from "@/components/uc3/monat";
import { laufPfad, regelsatzAus, uebersichtPfad, type Regelsatz } from "@/components/uc3/navigation";
import { regelsatzSatz } from "./_teile/regelsatz-satz";
import type { Monatslauf } from "@/components/uc3/typen";
import { Monatsgrafik } from "./_teile/monatsgrafik";
import { Monatsliste, type Zeile } from "./_teile/monatsliste";

// Monate (UI-Regie v1): eine Hauptaussage (wie viele Monate gerechnet, wie viele warten), eine Grafik der 24
// Monate, die angehaltenen Monate als eigener Block mit Grund und Rückfrage, eine Hauptaktion zum Vorführmonat,
// darunter die Liste. Liest die UC3-Datenbank direkt; ohne Datenbank zeigt die Seite den Leerzustand (HTTP 200).
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Monate · StatAgent" };

const ZAHLWORT = ["Kein Monat", "Einer", "Zwei", "Drei", "Vier", "Fünf"];

/** Kleiner Umschalter v1 | v2; erscheint erst, wenn es Läufe mit Regelsatz v2 gibt. */
function RegelsatzWahl({ aktiv }: { aktiv: Regelsatz }) {
  const punkte: Array<[Regelsatz, string, string]> = [
    ["v1", "v1", "Regelsatz v1: gezählt nach der Fachbeschreibung."],
    ["v2", "v2", "Regelsatz v2: gezählt mit den freigegebenen Änderungsaufträgen."],
  ];
  return (
    <nav aria-label="Regelsatz" className="flex items-center gap-2 font-sans text-14 text-slate">
      <span>Regelsatz</span>
      <ul className="flex overflow-hidden rounded-md border border-line">
        {punkte.map(([wert, text, erklaerung]) => (
          <li key={wert}>
            <Link
              href={uebersichtPfad(wert)}
              title={erklaerung}
              aria-current={wert === aktiv ? "page" : undefined}
              className={`inline-flex min-h-11 min-w-11 items-center justify-center px-3 ${wert === aktiv ? "bg-ink text-white" : "text-ink hover:bg-paper"}`}
            >
              {text}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Beleg der ganzen Zeitreihe: maßgeblicher Lauf je Monat mit Bestand und Abrechnung. */
function sqlZeitreihe(regelsatz: string): string {
  return [
    "SELECT lieferung, gezaehlt AS beschaeftigungsverhaeltnisse, fortgeschrieben, gelesen, nicht_gezaehlt,",
    "       ausgeschlossen, ergebnis_status",
    `FROM (${MASSGEBLICH_SQL.replace("$1", literal(regelsatz)).split("\n").join("\n      ")}) m`,
    "ORDER BY lieferung;",
  ].join("\n");
}

type Props = { searchParams: Promise<{ regelsatz?: string | string[] }> };

type Angehalten = { monat: Monatslauf; grund: string; wartet: string[]; beleg: ReturnType<typeof laufBeleg> | null };

async function angehalteneMonate(monate: readonly Monatslauf[], regelsatz: string): Promise<Angehalten[]> {
  const liste = monate.filter((m) => m.angehalten);
  return Promise.all(
    liste.map(async (monat) => {
      const lesung = await leseLaufDetail(monat.lieferung, regelsatz);
      const detail = lesung.ok ? lesung.daten : null;
      const halt = detail ? haltTreffer(detail.treffer) : null;
      return {
        monat,
        grund: halt && detail ? haltKurz(halt, detail.fdCodes) : "eine Prüfung hält an",
        wartet: detail?.veroeffentlichen.wartetAuf ?? [],
        beleg: halt && detail ? laufBeleg(detail.lauf, { quelle: "meta.pruefung_treffer", sql: sqlTreffer(detail.lauf, halt) }) : null,
      };
    }),
  );
}

export default async function Monate({ searchParams }: Props) {
  const regelsatz = regelsatzAus((await searchParams).regelsatz);
  const lesung = await leseMonatsuebersicht(regelsatz);

  if (!lesung.ok) return <DatenFehler grund={lesung.grund} />;
  if (lesung.daten.monate.length === 0) {
    const ohneV2 = lesung.ok && regelsatz === "v2";
    return (
      <>
        <Ueberschrift stufe={2} als="h1">
          {ohneV2 ? "Mit Regelsatz v2 ist noch kein Monat gerechnet." : "Noch kein Monat ist gerechnet."}
        </Ueberschrift>
        <Leerzustand
          satz={
            ohneV2
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

  const { monate, regelsaetze } = lesung.daten;
  const letzter = monate.at(-1)!;
  const angehalten = await angehalteneMonate(monate, regelsatz);
  const vorfuehren = angehalten.at(-1)?.monat;
  const wieViele = angehalten.length;
  const beideRegelsaetze = regelsaetze.includes("v2") || regelsatz === "v2";
  const andere = beideRegelsaetze ? await leseMonatsuebersicht(regelsatz === "v1" ? "v2" : "v1") : null;
  const andereZahl = andere?.ok ? (andere.daten.monate.find((m) => m.lieferung === letzter.lieferung)?.gezaehlt ?? null) : null;
  const zeilen: Zeile[] = monate.map((monat) => {
    const davor = monate.find((m) => m.lieferung === verschieben(monat.lieferung, -1));
    return { monat, vormonat: davor ? davor.gezaehlt : null, gehtAuf: abrechnung(monat).gehtAuf };
  });

  return (
    <>
      <header className="flex max-w-4xl flex-col gap-3">
        <Ueberschrift stufe={2} als="h1" className="hyphens-auto break-words">
          {`${formatZahl(monate.length)} Monate gerechnet. ${
            wieViele === 0
              ? "Keiner wartet auf die Fachabteilung."
              : `${ZAHLWORT[wieViele] ?? formatZahl(wieViele)} ${wieViele === 1 ? "wartet" : "warten"} auf die Fachabteilung.`
          }`}
        </Ueberschrift>
        <div className="flex flex-wrap items-baseline gap-x-3 font-sans text-16 text-slate">
          <span>
            {regelsatz === "v2" ? `${monatName(letzter.lieferung)}: ` : `Ende ${monatName(letzter.lieferung)}: `}
            <span className="tabular-nums text-ink">{formatZahl(letzter.gezaehlt)}</span>
            {" Beschäftigungsverhältnisse"}
          </span>
          <BelegLink {...bestandBeleg(letzter)} />
        </div>
        {beideRegelsaetze && (
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <p className="max-w-2xl font-sans text-16 text-pretty text-slate">{regelsatzSatz(regelsatz, andereZahl)}</p>
            <RegelsatzWahl aktiv={regelsatz} />
          </div>
        )}
      </header>

      <Monatsgrafik monate={monate} regelsatz={regelsatz} />

      {angehalten.length > 0 && (
        <section aria-labelledby="angehalten-titel" className="flex max-w-5xl flex-col gap-2">
          <h2 id="angehalten-titel" className="font-sans text-16 font-semibold text-ink">
            Angehalten
          </h2>
          <ul className="flex flex-col">
            {angehalten.map((a) => (
              <li
                key={a.monat.lieferung}
                className="flex flex-col gap-2 border-b border-line py-3 font-sans text-16 md:grid md:grid-cols-[10rem_1fr_auto] md:items-center md:gap-6"
              >
                <span className="font-medium text-ink">{monatName(a.monat.lieferung)}</span>
                <span className="flex flex-wrap gap-x-4">
                  <span className="text-ink">{a.grund}</span>
                  <span className="text-slate">
                    {a.wartet.length > 0 ? `wartet auf Rückfrage ${a.wartet.join(", ")}` : "wartet auf die Fachabteilung"}
                  </span>
                </span>
                <span className="flex items-center justify-end gap-4">
                  {a.beleg && <BelegLink {...a.beleg} />}
                  {a.monat.lieferung === vorfuehren?.lieferung ? (
                    <Link href={laufPfad(a.monat.lieferung, regelsatz)} className={knopfKlassen("primaer")}>
                      {`${monatName(a.monat.lieferung)} prüfen`}
                    </Link>
                  ) : (
                    <Link href={laufPfad(a.monat.lieferung, regelsatz)} className="inline-flex min-h-11 items-center font-medium text-ink underline underline-offset-4">
                      Prüfen
                    </Link>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="monate-titel" className="flex flex-col gap-2">
        <Monatsliste
          zeilen={zeilen}
          regelsatz={regelsatz}
          titel={
            <h2 id="monate-titel" className="font-sans text-16 font-semibold text-ink">
              Alle Läufe, je Monat mit Qualitätsbericht
            </h2>
          }
          rechts={<BelegLink quelle="meta.lauf" sql={sqlZeitreihe(regelsatz)} />}
        />
      </section>
    </>
  );
}

