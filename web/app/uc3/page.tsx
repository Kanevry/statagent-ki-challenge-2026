import type { Metadata } from "next";
import Link from "next/link";
import { knopfKlassen, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { laufBeleg, literal } from "@/components/uc3/beleg";
import { BelegLink } from "@/components/uc3/beleg-link";
import { DatenFehler } from "@/components/uc3/daten-fehler";
import { abrechnung, leseMonatsuebersicht, MASSGEBLICH_SQL } from "@/components/uc3/laeufe";
import { haltKurz, haltTreffer, leseLaufDetail, sqlTreffer } from "@/components/uc3/lauf-detail";
import { kopfSatz, leseDashboard } from "@/components/uc3/dashboard";
import { monatName, verschieben } from "@/components/uc3/monat";
import { laufPfad, regelsatzAus, uebersichtPfad } from "@/components/uc3/navigation";
import { mitRegeln, satzAnfang } from "@/components/uc3/regelsatz-name";
import { RegelsatzWahl } from "@/components/uc3/regelsatz-wahl";
import type { Monatslauf } from "@/components/uc3/typen";
import { Aufteilungen } from "./_teile/aufteilungen";
import { Kennzahlen } from "./_teile/kennzahlen";
import { Monatsgrafik } from "./_teile/monatsgrafik";
import { Monatsliste, type Zeile } from "./_teile/monatsliste";

// Dashboard (Bereich 4, Optimum): eine Hauptaussage, die Kurve der 24 Monate, vier Kennzahlen, die angehaltenen Monate
// mit Grund und Rückfrage als Hauptaktion, die Aufteilungen des letzten Monats, darunter die Liste. Liest die
// UC3-Datenbank direkt; ohne Datenbank zeigt die Seite den Leerzustand (HTTP 200). Antwortet nur der Zusatz nicht,
// fehlen Kennzahlen und Aufteilungen, der Rest bleibt.
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Dashboard · StatAgent" };

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
    const ohneLauf = lesung.ok && regelsatz !== "v1";
    return (
      <>
        <Ueberschrift stufe={2} als="h1">
          {ohneLauf ? `${satzAnfang(mitRegeln(regelsatz))} ist noch kein Monat gerechnet.` : "Noch kein Monat ist gerechnet."}
        </Ueberschrift>
        <Leerzustand
          satz={
            ohneLauf
                ? "Die Monate entstehen, sobald eine Änderung mit Namen freigegeben und gerechnet ist."
                : "Der erste Lauf beginnt mit August 2024."
          }
          aktion={
            ohneLauf ? (
              <Link href={uebersichtPfad("v1")} className={knopfKlassen("sekundaer")}>
                Monate nach den alten Regeln ansehen
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
  const beideRegelsaetze = regelsaetze.includes("v2") || regelsatz !== "v1";
  const andere = beideRegelsaetze ? await leseMonatsuebersicht(regelsatz === "v1" ? "v2" : "v1") : null;
  const andereZahl = andere?.ok ? (andere.daten.monate.find((m) => m.lieferung === letzter.lieferung)?.gezaehlt ?? null) : null;
  const zusatz = await leseDashboard(letzter, regelsatz);
  const dashboard = zusatz.ok ? zusatz.daten : null;
  const zeilen: Zeile[] = monate.map((monat) => {
    const davor = monate.find((m) => m.lieferung === verschieben(monat.lieferung, -1));
    return { monat, vormonat: davor ? davor.gezaehlt : null, gehtAuf: abrechnung(monat).gehtAuf };
  });

  return (
    <>
      <header className="flex max-w-4xl flex-col gap-3">
        <p className="font-sans text-16 font-semibold text-ink">Dashboard der Beschäftigtenstatistik</p>
        <Ueberschrift stufe={2} als="h1" className="hyphens-auto break-words">
          {kopfSatz(monate)}
        </Ueberschrift>
        {beideRegelsaetze && <RegelsatzWahl aktiv={regelsatz} pfad={uebersichtPfad} andereZahl={andereZahl} />}
      </header>

      <Monatsgrafik key={regelsatz} monate={monate} regelsatz={regelsatz} beleg={<BelegLink quelle="meta.lauf" sql={sqlZeitreihe(regelsatz)} />} />

      {dashboard && (
        <Kennzahlen monate={monate} vormonat={zeilen.at(-1)?.vormonat ?? null} treffer={dashboard.detail.treffer} einstufungen={dashboard.einstufungen} />
      )}

      {angehalten.length > 0 && (
        <section aria-labelledby="angehalten-titel" className="flex max-w-5xl flex-col gap-2">
          <h2 id="angehalten-titel" className="font-sans text-16 font-semibold text-ink">
            Angehalten
          </h2>
          <p className="max-w-3xl font-sans text-16 text-slate">
            Angehalten heißt: Eine Prüfung hat beim Rechnen etwas so Großes gefunden, dass ein Mensch entscheiden muss.
          </p>
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
                      {`Bericht ${monatName(a.monat.lieferung)} ansehen`}
                    </Link>
                  ) : (
                    <Link href={laufPfad(a.monat.lieferung, regelsatz)} className="inline-flex min-h-11 items-center font-medium text-ink underline underline-offset-4">
                      Bericht ansehen
                    </Link>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {dashboard && <Aufteilungen lauf={dashboard.detail.lauf} regionen={dashboard.detail.regionen} geschlecht={dashboard.geschlecht} />}

      <section aria-labelledby="monate-titel" className="flex flex-col gap-2">
        <Monatsliste
          zeilen={zeilen}
          regelsatz={regelsatz}
          titel={
            <h2 id="monate-titel" className="font-sans text-16 font-semibold text-ink">
              Alle Läufe, je Monat mit Qualitätsbericht
            </h2>
          }
          rechts={
            <>
              <Link href="/uc3/ergebnisse" className="inline-flex min-h-11 items-center font-sans text-14 font-medium text-ink underline underline-offset-4 hover:text-gruen">
                Excel-Dateien herunterladen
              </Link>
              <BelegLink quelle="meta.lauf" sql={sqlZeitreihe(regelsatz)} />
            </>
          }
        />
      </section>
    </>
  );
}

