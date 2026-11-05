"use client";

import Link from "next/link";
import { knopfKlassen } from "@kic/ui/basis";
import type { Modus } from "../../../app/api/uc2/_lib/proxy";
import { FreigabeBericht, useEntscheidung } from "../freigabe";
import { akteurName, klartext, monatText, themaKurz } from "../namen";
import { endstand, type FallZustand } from "../zustand";
import { Brett } from "./brett";
import { buehneAus, ersterSatz, haltungWort, hauptaussage, kategorieWort, kuerzel, type Buehne } from "./takt";
import { useWiedergabe } from "./use-wiedergabe";
import css from "./buehne.module.css";

// Die Bühne des Panels: links genau eine Sache (wer spricht, was er sagt, was sich dadurch ändert), rechts das Brett
// mit allen Haltungen. Alles andere (ganzer Verlauf, alle Belege) liegt hinter "Ganzer Verlauf".

const PHASE: Record<string, string> = {
  position: "Positionen",
  debatte: "Debatte",
  verhandlung: "Verhandlung",
  kompromiss: "Kompromiss",
};

function zahl(wert: number, stellen = 1): string {
  return new Intl.NumberFormat("de-AT", { maximumFractionDigits: stellen, minimumFractionDigits: 0 }).format(wert);
}

function prozent(wert: number): string {
  return `${wert > 0 ? "+" : wert < 0 ? "−" : ""}${zahl(Math.abs(wert))} %`;
}

export function PanelBuehne({ fallId, modus }: { fallId: string; modus: Modus }) {
  const w = useWiedergabe(fallId);
  const z = w.zustand;
  const buehne = buehneAus(w.gezeigt, z);
  const sprecher = buehne.art === "zug" ? buehne.akteur : null;
  const rundeNr = buehne.runde ?? z.runden.at(-1)?.nr ?? null;
  const phase = z.runden.find((r) => r.nr === rundeNr)?.phase;
  const fertig = buehne.art === "ergebnis";

  if (w.verbindung === "nicht-gefunden") {
    return (
      <Rahmen>
        <h1 className="font-display text-28 font-bold text-ink">Diese Verhandlung gibt es nicht.</h1>
        <Link href="/uc2" className={knopfKlassen()}>
          Zum Fall
        </Link>
      </Rahmen>
    );
  }

  return (
    <div className="flex flex-col gap-8" data-testid="uc2-buehne">
      <header className="flex flex-col gap-3">
        <p className="max-w-3xl font-sans text-16 text-slate">{z.frage ?? "Die Verhandlung wird geladen."}</p>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="font-display text-28 font-bold text-ink" aria-live="polite">
            {fertig
              ? `Ergebnis nach ${z.ergebnis?.runden ?? z.runden.length} Runden`
              : rundeNr
                ? `Runde ${rundeNr}${z.maxRunden ? ` von höchstens ${z.maxRunden}` : ""}${phase ? `: ${PHASE[phase] ?? phase}` : ""}`
                : "Das Panel setzt sich an den Tisch"}
          </h1>
          {!fertig && (
            <div className="flex items-center gap-2">
              <button type="button" onClick={w.umschalten} className={knopfKlassen("sekundaer")}>
                {w.pausiert ? "Weiter" : "Anhalten"}
              </button>
              <button
                type="button"
                onClick={() => w.setTempo(w.tempo === 1 ? 2 : 1)}
                className={knopfKlassen("sekundaer")}
                aria-label={w.tempo === 1 ? "Doppelt so schnell" : "Normales Tempo"}
              >
                {w.tempo === 1 ? "2×" : "1×"}
              </button>
              <button type="button" onClick={w.zumEnde} className="h-11 px-2 font-sans text-14 text-gruen underline underline-offset-4">
                Zum Ergebnis
              </button>
            </div>
          )}
        </div>
        <div className="h-1 w-full overflow-hidden rounded-full bg-line" aria-hidden="true">
          <div className="h-full bg-gruen transition-[width] duration-500 motion-reduce:transition-none" style={{ width: `${Math.round(w.anteil * 100)}%` }} />
        </div>
        {/* KI-Kennzeichnung ab dem ersten Zug, nicht erst im Abschluss (AI Act Art. 50, Review !101). */}
        <ModellZeile modus={modus} zustand={z} />
        {w.verbindung === "unterbrochen" && (
          <p role="alert" className="flex flex-wrap items-center gap-3 font-sans text-16 text-ink">
            Die Verbindung ist unterbrochen. Was schon da war, bleibt stehen.
            <button type="button" onClick={w.neuVerbinden} className={knopfKlassen("sekundaer")}>
              Neu verbinden
            </button>
          </p>
        )}
      </header>

      <Sitzreihe gruppen={z.teilnehmer} sprecher={sprecher} moderator={buehne.art === "moderator"} experte={buehne.art === "experte"} />

      <div className="grid gap-10 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <div className="flex flex-col justify-between gap-10">
          <div className="min-h-[200px] lg:min-h-[300px]" aria-live="polite">
            <Szene buehne={buehne} zustand={z} />
          </div>
          {z.experte && buehne.art !== "experte" && <ExperteKurz zustand={z} />}
        </div>
        <Brett zustand={z} sprecher={sprecher} />
      </div>

      {fertig && <Abschluss fallId={fallId} modus={modus} zustand={z} onVonVorn={w.vonVorn} />}

      {(fertig || w.pausiert) && <Verlauf zustand={fertig ? z : w.gesamt} />}
    </div>
  );
}

/** Woher die Sätze der Gruppen kommen: aufgezeichnet ohne Modell oder das Modell des Laufs. */
export function modellSatz(modus: Modus, z: FallZustand): string {
  const akteur = z.modelle?.akteur;
  if (modus === "live" && akteur?.modell && akteur.provider !== "mock") {
    return `Die Sätze der Gruppen schreibt eine KI (${akteur.provider ?? ""} ${akteur.modell}). Die Zahlen rechnet der Experte ohne KI.`;
  }
  // Live, aber das Ereignis „start“ mit den Modellen ist noch nicht da: nichts behaupten (Review !101).
  if (modus === "live" && !akteur) return "Die Verhandlung startet.";
  return "Aufgezeichnete Verhandlung mit Beispiel-Belegen, ohne Sprachmodell.";
}

function ModellZeile({ modus, zustand }: { modus: Modus; zustand: FallZustand }) {
  return (
    <p className="font-sans text-12 text-slate" data-testid="uc2-modell-satz">
      {modellSatz(modus, zustand)}
    </p>
  );
}

function Rahmen({ children }: { children: React.ReactNode }) {
  return <div className="flex min-h-[50vh] flex-col items-start justify-center gap-6">{children}</div>;
}

function Sitzreihe({ gruppen, sprecher, moderator, experte }: { gruppen: string[]; sprecher: string | null; moderator: boolean; experte: boolean }) {
  if (gruppen.length === 0) return null;
  const sitz = (id: string, name: string, aktiv: boolean, kurz?: string) => (
    <li
      key={id}
      className={
        "flex items-center gap-2 border-b-2 pb-2 font-sans text-14 transition-colors duration-300 motion-reduce:transition-none " +
        (aktiv ? "border-gruen font-semibold text-ink" : "border-transparent text-slate")
      }
      aria-current={aktiv ? "true" : undefined}
    >
      {kurz && (
        <span
          aria-hidden="true"
          className={
            "flex h-[26px] w-[26px] items-center justify-center rounded-full border text-11 font-semibold " +
            (aktiv ? "border-ink bg-ink text-white" : "border-line bg-white text-slate")
          }
        >
          {kurz}
        </span>
      )}
      <span className={kurz && !aktiv ? "sr-only sm:not-sr-only" : undefined}>{name}</span>
    </li>
  );
  return (
    <nav aria-label="Am Tisch">
      <ul className="flex flex-wrap gap-x-5 gap-y-3 border-b border-line">
        {gruppen.map((g) => sitz(g, akteurName(g), g === sprecher, kuerzel(g)))}
        <li className="ml-auto" aria-hidden="true" />
        {sitz("moderator", "Moderator", moderator)}
      </ul>
    </nav>
  );
}

function Szene({ buehne, zustand: z }: { buehne: Buehne; zustand: FallZustand }) {
  switch (buehne.art) {
    case "auftakt":
      return (
        <Auftritt schluessel="auftakt" wer="Moderator" satz="Sechs Gruppen setzen sich an den Tisch. Jede bringt ihre Belege aus der Presse mit." />
      );
    case "experte": {
      const e = z.experte;
      return (
        <Auftritt
          schluessel="experte"
          wer="Experte, rechnet ohne KI"
          satz={e?.beschreibung ? `Das Paket: ${klartext(e.beschreibung)}.` : "Der Experte rechnet das Paket durch."}
        >
          {e?.wartezeit_aenderung_prozent && e.kosten_aenderung_prozent && (
            <dl className="grid grid-cols-2 gap-6">
              <Kennzahl titel="Wartezeit" wert={prozent(e.wartezeit_aenderung_prozent.modus)} />
              <Kennzahl titel="Ausgaben" wert={prozent(e.kosten_aenderung_prozent.modus)} />
            </dl>
          )}
        </Auftritt>
      );
    }
    case "runde": {
      const r = z.runden.find((x) => x.nr === buehne.runde);
      return (
        <Auftritt
          schluessel={`runde-${buehne.runde}`}
          wer="Moderator"
          satz={
            buehne.runde === 1
              ? "Runde 1: Jede Gruppe sagt, wo sie steht."
              : `Runde ${buehne.runde}: ${r?.phase === "kompromiss" ? "Wer kann nachgeben?" : "Die Gruppen antworten aufeinander."}`
          }
        />
      );
    }
    case "zug": {
      const akteur = buehne.akteur!;
      const runden = z.runden.filter((r) => r.zuege[akteur]);
      const zug = runden.at(-1)?.zuege[akteur];
      const davor = runden.at(-2)?.zuege[akteur];
      const aussage = zug ? hauptaussage(zug, davor) : null;
      const beleg = aussage?.belegIds.map((id) => z.belegIndex[id]).find(Boolean);
      const pruefung = z.hinweise.find((h) => h.akteur === akteur && h.runde === buehne.runde);
      return (
        <Auftritt schluessel={`zug-${buehne.runde}-${akteur}`} wer={akteurName(akteur)}>
          {aussage && (
            <>
              <p className="font-sans text-16 text-slate">
                {aussage.titel}:{" "}
                {aussage.vorher !== null && aussage.vorher !== aussage.haltung ? (
                  <>
                    <span className="line-through decoration-slate/60">{haltungWort(aussage.vorher)}</span>{" "}
                    <span className="font-semibold text-ink">jetzt {haltungWort(aussage.haltung)}</span>
                  </>
                ) : (
                  <span className="font-semibold text-ink">{haltungWort(aussage.haltung)}</span>
                )}
              </p>
              <blockquote className="font-display text-20 font-medium break-words text-ink text-pretty hyphens-auto sm:text-28">„{aussage.satz}“</blockquote>
              {beleg && (
                <details className="group max-w-xl">
                  <summary className="inline-flex min-h-11 cursor-pointer items-center font-sans text-14 text-gruen underline underline-offset-4">
                    Beleg: {klartext(beleg.medium)}
                    {beleg.monat || beleg.datum ? `, ${monatText(beleg.monat ?? beleg.datum)}` : ""}
                  </summary>
                  <p className="mt-2 font-sans text-14 text-slate">„{klartext(beleg.zitat)}“</p>
                </details>
              )}
              {pruefung && <p className="font-sans text-14 text-warn-fg">Prüfung: {pruefung.text}</p>}
            </>
          )}
        </Auftritt>
      );
    }
    case "moderator": {
      const notiz = z.runden.find((r) => r.nr === buehne.runde)?.notiz;
      return <Auftritt schluessel={`mod-${buehne.runde}`} wer="Moderator" satz={notiz ? ersterSatz(notiz.text, 220) : "Der Moderator fasst zusammen."} />;
    }
    case "runde_ende": {
      const r = z.runden.find((x) => x.nr === buehne.runde);
      const aenderungen = r?.ende?.aenderungen ?? [];
      return (
        <Auftritt
          schluessel={`ende-${buehne.runde}`}
          wer={`Nach Runde ${buehne.runde}`}
          satz={
            aenderungen.length === 0
              ? "Niemand hat sich bewegt."
              : `${aenderungen.length === 1 ? "Eine Gruppe hat" : `${aenderungen.length}-mal haben Gruppen`} ihre Haltung geändert.`
          }
        >
          {aenderungen.length > 0 && (
            <ul className="flex flex-col gap-2">
              {aenderungen.slice(0, 5).map((a) => (
                <li key={`${a.akteur}-${a.thema}`} className="font-sans text-16 text-ink">
                  {akteurName(a.akteur)} bei {themaKurz(a.thema)}: {haltungWort(a.alt)} → {haltungWort(a.neu)}
                </li>
              ))}
            </ul>
          )}
        </Auftritt>
      );
    }
    case "ergebnis":
      return <Ergebnis zustand={z} />;
    case "abbruch":
      return (
        <Auftritt
          schluessel="abbruch"
          wer="Moderator"
          satz={z.fehler?.meldung ?? "Die Verhandlung wurde abgebrochen, weil ein Modell nicht geantwortet hat."}
        >
          <Link href="/uc2" className={knopfKlassen("sekundaer")}>
            Zurück zum Fall
          </Link>
        </Auftritt>
      );
  }
}

/** Ein Auftritt: wer spricht, ein großer Satz, darunter höchstens ein Baustein. Blendet beim Wechsel einmal ein. */
function Auftritt({ schluessel, wer, satz, children }: { schluessel: string; wer: string; satz?: string; children?: React.ReactNode }) {
  return (
    <article key={schluessel} className={`flex flex-col gap-5 ${css.auftritt}`}>
      <p className="font-sans text-14 font-semibold text-gruen">{wer}</p>
      {satz && <p className="font-display text-20 font-medium break-words text-ink text-pretty hyphens-auto sm:text-28">{satz}</p>}
      {children}
    </article>
  );
}

function Kennzahl({ titel, wert }: { titel: string; wert: string }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="font-sans text-14 text-slate">{titel}</dt>
      <dd className="font-display text-32 font-bold text-ink tabular-nums sm:text-56">{wert}</dd>
    </div>
  );
}

function ExperteKurz({ zustand: z }: { zustand: FallZustand }) {
  const e = z.experte!;
  const w = e.wartezeit_aenderung_prozent;
  const k = e.kosten_aenderung_prozent;
  return (
    <section aria-labelledby="experte-titel" className="flex flex-col gap-2 border-t border-line pt-5">
      <h2 id="experte-titel" className="font-display text-20 font-bold text-ink">
        Was das Paket bringt
      </h2>
      {w && k && (
        <p className="font-sans text-16 text-ink">
          Wartezeit {prozent(w.modus)}, Ausgaben {prozent(k.modus)}. Das Ziel ist −20 % bei höchstens +5 %.
        </p>
      )}
      {w && (
        <p className="font-sans text-14 text-slate">
          Im ungünstigen Fall sinkt die Wartezeit nur um {zahl(Math.abs(w.max))} %, dann wird das Ziel verfehlt. Gerechnet vom
          Experten ohne KI.
        </p>
      )}
    </section>
  );
}

const REIHENFOLGE = ["konsens", "mehrheit", "offener_konflikt", "abgelehnt"];

function schluss(z: FallZustand): string {
  const grund = z.ergebnis?.abbruch ?? "";
  const runde = /Runde (\d+) ohne Positions/.exec(grund);
  if (runde) return `In Runde ${runde[1]} hat sich niemand mehr bewegt.`;
  return grund ? `${klartext(grund)}.` : "";
}

function Ergebnis({ zustand: z }: { zustand: FallZustand }) {
  const stand = [...(endstand(z) ?? [])].sort((a, b) => REIHENFOLGE.indexOf(a.kategorie) - REIHENFOLGE.indexOf(b.kategorie));
  return (
    <article className={`flex flex-col gap-6 ${css.auftritt}`}>
      <p className="font-sans text-14 font-semibold text-gruen">Moderator</p>
      <p className="font-display text-20 font-medium break-words text-ink text-pretty hyphens-auto sm:text-28">
        {stand.filter((t) => t.kategorie === "konsens" || t.kategorie === "mehrheit").length} von {stand.length} Themen haben eine
        Mehrheit. {schluss(z)}
      </p>
      <ul className="flex flex-col divide-y divide-line border-y border-line">
        {stand.map((t) => (
          <li key={t.thema} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
            <span className="font-sans text-16 font-semibold text-ink">{themaKurz(t.thema)}</span>
            <span className="font-sans text-16 text-ink">
              {kategorieWort(t.kategorie)}
              {t.dagegen.length > 0 && <span className="text-slate">, dagegen: {t.dagegen.map(akteurName).join(", ")}</span>}
            </span>
          </li>
        ))}
      </ul>
    </article>
  );
}

function Abschluss({ fallId, modus, zustand: z, onVonVorn }: { fallId: string; modus: Modus; zustand: FallZustand; onVonVorn: () => void }) {
  const [entscheidung, setEntscheidung] = useEntscheidung(fallId, modus, z.status === "fertig");
  return (
    <section className="flex flex-col gap-4 border-t border-line pt-8">
      <div className="max-w-2xl">
        <FreigabeBericht fallId={fallId} modus={modus} entscheidung={entscheidung} onEntschieden={setEntscheidung} />
      </div>
      <p className="font-sans text-14 text-slate">
        <button type="button" onClick={onVonVorn} className="min-h-11 text-gruen underline underline-offset-4">
          Noch einmal ansehen
        </button>
      </p>
    </section>
  );
}

function Verlauf({ zustand: z }: { zustand: FallZustand }) {
  return (
    <details className="border-t border-line pt-6">
      <summary className="inline-flex min-h-11 cursor-pointer items-center font-sans text-16 font-semibold text-ink">Ganzer Verlauf</summary>
      <ol className="mt-4 flex flex-col gap-6">
        {z.runden.map((r) => (
          <li key={r.nr} className="flex flex-col gap-2">
            <h3 className="font-sans text-16 font-semibold text-ink">
              Runde {r.nr}
              {r.phase ? `: ${PHASE[r.phase] ?? r.phase}` : ""}
            </h3>
            <ul className="flex flex-col gap-1">
              {Object.entries(r.zuege).map(([akteur, zug]) => (
                <li key={akteur} className="font-sans text-14 text-slate">
                  <span className="font-semibold text-ink">{akteurName(akteur)}:</span>{" "}
                  {Object.values(zug.themen)
                    .map((t) => `${themaKurz(t.thema)} ${haltungWort(t.haltung)}`)
                    .join(", ")}
                </li>
              ))}
            </ul>
            {r.notiz && <p className="font-sans text-14 text-slate">Moderator: {r.notiz.text}</p>}
          </li>
        ))}
      </ol>
    </details>
  );
}
