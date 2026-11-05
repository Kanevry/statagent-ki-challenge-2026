"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { HerkunftChip, ModellPille } from "@kic/ui/bausteine";
import { SeitenModell, TESTBETRIEB_TEXT } from "@kic/ui/shell";
import { findeUc } from "@kic/ui/ucs";
import { VOICE_KONFIGURATION_QUELLE, voiceKonfigurationSchema, type VoiceKonfiguration } from "@kic/ui/voice";
import type { UcAntwort } from "@kic/ui/antwortform";
import {
  frageSchema,
  grundText,
  MAX_FRAGE,
  MODELL_NAMEN,
  MODELLWAHL,
  STROM_TYP,
  stromEreignisSchema,
  type KettenUc,
  type Modellwahl,
} from "../../lib/plattform/uc4-ergebnis";
import { Stimme } from "./stimme";

// /uc4: eine Frage läuft durch die Stationen der Kette. Jede Station leuchtet auf, wenn sie arbeitet, und klappt ihre
// Antwort auf, sobald sie da ist (NDJSON-Strom, ein Ereignis je Zeile). Das Warten ist Teil der Vorführung: man sieht,
// wer gerade arbeitet und was er von der Station davor bekommen hat.

const ROLLE: Record<KettenUc, string> = {
  uc3: "rechnet die Zahl aus den Daten, ohne KI",
  uc2: "wägt ab, was das für die Versorgung heißt",
  uc1: "sagt in einfachen Worten, was es für Sie heißt",
};

const BEISPIELE = [
  "Wie viele Beschäftigte gab es im März 2025 in Wien im Gesundheits- und Sozialwesen?",
  "Wie viele Beschäftigte gab es im Oktober 2025?",
];

type Station =
  | { art: "wartet" }
  | { art: "laeuft"; seit: number }
  | { art: "antwort"; kern: string; antwort: UcAntwort; dauerMs: number }
  | { art: "fehlt"; grund: string };

type Lauf =
  | { art: "leer" }
  | { art: "laeuft"; stationen: Record<string, Station> }
  | { art: "fertig"; stationen: Record<string, Station>; dauerMs: number }
  | { art: "fehler"; meldung: string; stationen?: Record<string, Station> };

function sekunden(ms: number): string {
  return new Intl.NumberFormat("de-AT", { maximumFractionDigits: 1, minimumFractionDigits: 1 }).format(ms / 1000);
}

function leereStationen(kette: readonly KettenUc[]): Record<string, Station> {
  return Object.fromEntries(kette.map((uc) => [uc, { art: "wartet" } as Station]));
}

async function fehlerAusAntwort(antwort: Response): Promise<string> {
  if (antwort.status === 403 || antwort.status === 405) return "Fragen sind hier gerade nicht offen.";
  const daten: unknown = await antwort.json().catch(() => null);
  if (daten && typeof daten === "object" && "fehler" in daten && typeof daten.fehler === "string") return daten.fehler;
  return antwort.status === 429 ? "Gerade sind zu viele Fragen unterwegs. Bitte gleich noch einmal." : "Die Kette hat nicht geantwortet.";
}

/** Was der Screenreader am Ende hört: wie viele Stationen geantwortet haben, nicht pauschal „alle“. */
function fertigSatz(stationen: Record<string, Station>): string {
  const alle = Object.values(stationen);
  const mit = alle.filter((s) => s.art === "antwort").length;
  if (mit === alle.length) return mit === 1 ? "Die Station hat geantwortet." : `Alle ${mit} Stationen haben geantwortet.`;
  return `${mit} von ${alle.length} Stationen haben geantwortet.`;
}

function useSprache(): VoiceKonfiguration | null {
  const [konfig, setKonfig] = useState<VoiceKonfiguration | null>(null);
  useEffect(() => {
    const abbruch = new AbortController();
    fetch(VOICE_KONFIGURATION_QUELLE, { signal: abbruch.signal, cache: "no-store" })
      .then(async (r) => {
        const g = voiceKonfigurationSchema.safeParse(await r.json());
        if (g.success && g.data.aktiv) setKonfig(g.data);
      })
      .catch(() => undefined);
    return () => abbruch.abort();
  }, []);
  return konfig;
}

export function Kette({ kette, fragenOffen, mitModell }: { kette: readonly KettenUc[]; fragenOffen: boolean; mitModell: boolean }) {
  const [frage, setFrage] = useState("");
  const [modell, setModell] = useState<Modellwahl | null>(null);
  const [eingabeFehler, setEingabeFehler] = useState<string | null>(null);
  const [lauf, setLauf] = useState<Lauf>({ art: "leer" });
  const [jetzt, setJetzt] = useState(() => Date.now());
  const abbruch = useRef<AbortController | null>(null);
  const sprache = useSprache();
  const laeuft = lauf.art === "laeuft";

  // Sekundenanzeige der arbeitenden Station.
  useEffect(() => {
    if (!laeuft) return;
    const uhr = setInterval(() => setJetzt(Date.now()), 200);
    return () => clearInterval(uhr);
  }, [laeuft]);

  useEffect(() => () => abbruch.current?.abort(), []);

  async function fragen(text: string) {
    const geprueft = frageSchema.safeParse({ frage: text });
    if (!geprueft.success) {
      setEingabeFehler(geprueft.error.issues[0]?.message ?? "Bitte eine Frage eingeben.");
      return;
    }
    setEingabeFehler(null);
    abbruch.current?.abort();
    const steuerung = new AbortController();
    abbruch.current = steuerung;
    let stationen = leereStationen(kette);
    setLauf({ art: "laeuft", stationen });

    let antwort: Response;
    try {
      antwort = await fetch("/api/uc4/frage", {
        method: "POST",
        headers: { "content-type": "application/json", accept: STROM_TYP },
        body: JSON.stringify(modell && mitModell ? { frage: geprueft.data.frage, modell } : { frage: geprueft.data.frage }),
        cache: "no-store",
        signal: steuerung.signal,
      });
    } catch {
      if (!steuerung.signal.aborted) setLauf({ art: "fehler", meldung: "Keine Verbindung zum Server." });
      return;
    }
    if (!antwort.ok || !antwort.body) {
      setLauf({ art: "fehler", meldung: await fehlerAusAntwort(antwort) });
      return;
    }

    const leser = antwort.body.getReader();
    const dekoder = new TextDecoder();
    let rest = "";
    // Endet der Strom ohne „ende“ oder „fehler“ oder kommt eine unlesbare Zeile, ist der Lauf kaputt: dann ein
    // Fehlersatz statt einer Seite, die ewig „läuft“ (Review !106).
    let abgeschlossen = false;
    let kaputt = false;
    const anwenden = (zeile: string) => {
      if (!zeile.trim() || abgeschlossen) return;
      let roh: unknown;
      try {
        roh = JSON.parse(zeile);
      } catch {
        kaputt = true;
        return;
      }
      const e = stromEreignisSchema.safeParse(roh);
      if (!e.success) {
        kaputt = true;
        return;
      }
      const d = e.data;
      switch (d.art) {
        case "start":
          stationen = leereStationen(d.kette);
          setLauf({ art: "laeuft", stationen });
          return;
        case "station":
          stationen = { ...stationen, [d.uc]: { art: "laeuft", seit: Date.now() } };
          setLauf({ art: "laeuft", stationen });
          return;
        case "antwort":
          stationen = { ...stationen, [d.uc]: { art: "antwort", kern: d.kern, antwort: d.antwort, dauerMs: d.dauer_ms } };
          setLauf({ art: "laeuft", stationen });
          return;
        case "fehlt":
          stationen = { ...stationen, [d.uc]: { art: "fehlt", grund: d.grund } };
          setLauf({ art: "laeuft", stationen });
          return;
        case "ende":
          abgeschlossen = true;
          setLauf({ art: "fertig", stationen, dauerMs: d.dauer_ms });
          return;
        case "fehler":
          abgeschlossen = true;
          setLauf({ art: "fehler", meldung: d.fehler, stationen });
          return;
      }
    };
    try {
      for (;;) {
        const { done, value } = await leser.read();
        if (done) break;
        rest += dekoder.decode(value, { stream: true });
        const zeilen = rest.split("\n");
        rest = zeilen.pop() ?? "";
        zeilen.forEach(anwenden);
      }
      anwenden(rest);
      if (!abgeschlossen && !steuerung.signal.aborted) {
        setLauf({
          art: "fehler",
          meldung: kaputt ? "Die Antwort kam nicht im erwarteten Format." : "Die Antwort brach ab, bevor alle Stationen fertig waren.",
          stationen,
        });
      }
    } catch {
      if (!steuerung.signal.aborted) setLauf({ art: "fehler", meldung: "Die Verbindung ist abgerissen.", stationen });
    }
  }

  function absenden(ereignis: FormEvent<HTMLFormElement>) {
    ereignis.preventDefault();
    if (!laeuft) void fragen(frage);
  }

  const stationen = lauf.art === "leer" ? leereStationen(kette) : (lauf.stationen ?? leereStationen(kette));
  const modelle = [
    ...new Set(
      Object.values(stationen)
        .flatMap((s) => (s.art === "antwort" && s.antwort.modell ? [s.antwort.modell] : []))
        .filter((m) => m !== "mock"),
    ),
  ];

  return (
    <div className="flex flex-col gap-10" data-testid="uc4-kette">
      {fragenOffen ? (
        <form onSubmit={absenden} className="flex max-w-4xl flex-col gap-3" noValidate>
          <label htmlFor="uc4-frage" className="font-sans text-14 font-semibold text-ink">
            Ihre Frage
          </label>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              id="uc4-frage"
              name="frage"
              value={frage}
              maxLength={MAX_FRAGE}
              onChange={(e) => setFrage(e.target.value)}
              placeholder="Wie viele Beschäftigte gab es im März 2025?"
              aria-invalid={eingabeFehler ? true : undefined}
              aria-describedby={eingabeFehler ? "uc4-frage-fehler" : undefined}
              className="min-h-14 flex-1 rounded-lg border border-ink/30 bg-white px-4 font-sans text-20 text-ink placeholder:text-slate/70 focus-visible:border-gruen focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen"
            />
            <button
              type="submit"
              disabled={laeuft}
              className="inline-flex min-h-14 items-center justify-center rounded-lg bg-gruen px-6 font-sans text-16 font-semibold text-white hover:bg-gruen-dunkel disabled:opacity-60"
            >
              {laeuft ? "Läuft …" : "Fragen"}
            </button>
          </div>
          {eingabeFehler && (
            <p id="uc4-frage-fehler" className="font-sans text-14 text-err-fg">
              {eingabeFehler}
            </p>
          )}
          <div className="flex flex-col gap-1">
            <p className="font-sans text-14 text-slate">Zum Beispiel:</p>
            <ul className="flex flex-col gap-x-8 lg:flex-row lg:flex-wrap">
              {BEISPIELE.map((b) => (
                <li key={b}>
                  <button
                    type="button"
                    disabled={laeuft}
                    onClick={() => {
                      setFrage(b);
                      void fragen(b);
                    }}
                    className="min-h-11 text-left font-sans text-16 text-gruen underline underline-offset-4 disabled:opacity-60"
                  >
                    {b}
                  </button>
                </li>
              ))}
            </ul>
          </div>
          {sprache && <Stimme konfiguration={sprache} />}
          {mitModell && (
            <details className="font-sans text-14 text-slate">
              <summary className="inline-flex min-h-11 cursor-pointer items-center underline underline-offset-4">Modell wählen</summary>
              <fieldset className="mt-2 flex flex-wrap gap-x-5 gap-y-2" disabled={laeuft}>
                <legend className="sr-only">Welches Modell schreibt die Sätze?</legend>
                {[{ wert: null as Modellwahl | null, name: "Voreinstellung" }, ...MODELLWAHL.map((wert) => ({ wert, name: MODELL_NAMEN[wert] }))].map(
                  ({ wert, name }) => (
                    <label key={name} className="inline-flex min-h-11 items-center gap-2 text-ink">
                      <input type="radio" name="modell" checked={modell === wert} onChange={() => setModell(wert)} className="size-4 accent-gruen" />
                      {name}
                    </label>
                  ),
                )}
              </fieldset>
            </details>
          )}
        </form>
      ) : (
        <p className="max-w-3xl font-display text-28 font-medium text-ink">Fragen an die Kette sind hier gerade nicht offen.</p>
      )}

      <p role="status" aria-live="polite" className="sr-only">
        {lauf.art === "laeuft" ? "Die Frage läuft durch die Kette." : lauf.art === "fertig" ? fertigSatz(lauf.stationen) : ""}
      </p>

      {lauf.art === "fehler" && !lauf.stationen && <p role="alert" className="font-sans text-16 text-ink">{lauf.meldung}</p>}

      <section aria-label="Stationen der Kette">
        <ol className={kette.length === 1 ? "grid max-w-2xl gap-6" : "grid gap-6 lg:grid-cols-3"}>
          {kette.map((uc, i) => (
            <StationKarte key={uc} uc={uc} nr={i + 1} station={stationen[uc] ?? { art: "wartet" }} jetzt={jetzt} vorher={i > 0 ? kette[i - 1] : undefined} gestellt={lauf.art !== "leer"} />
          ))}
        </ol>
      </section>

      {lauf.art === "fehler" && lauf.stationen && <p role="alert" className="font-sans text-16 text-ink">{lauf.meldung}</p>}
      {lauf.art === "fertig" && (
        <p className="font-sans text-14 text-slate">
          Fertig in {sekunden(lauf.dauerMs)} s.{" "}
          {modelle.length > 0 ? `Die Sätze schreibt ${modelle.join(" und ")}, die Zahlen rechnet der Code.` : "Die Zahlen rechnet der Code."}
        </p>
      )}
      {modelle.length === 1 && <SeitenModell provider={modelle[0]!} gewaehlt />}
    </div>
  );
}

function StationKarte({
  uc,
  nr,
  station,
  jetzt,
  vorher,
  gestellt,
}: {
  uc: KettenUc;
  nr: number;
  station: Station;
  jetzt: number;
  vorher?: KettenUc;
  gestellt: boolean;
}) {
  const name = findeUc(uc).name;
  const aktiv = station.art === "laeuft";
  const fertig = station.art === "antwort";
  return (
    <li
      data-uc-karte={uc}
      data-zustand={station.art}
      className={
        "flex flex-col gap-4 rounded-lg border bg-white p-5 transition-[border-color,opacity] duration-500 motion-reduce:transition-none md:p-6 " +
        (aktiv ? "border-gruen" : fertig ? "border-line" : "border-line") +
        (gestellt && station.art === "wartet" ? " opacity-50" : "")
      }
    >
      <div className="flex items-baseline gap-3">
        <span
          aria-hidden="true"
          className={
            "flex size-8 shrink-0 items-center justify-center rounded-full font-display text-16 font-bold transition-colors duration-500 motion-reduce:transition-none " +
            (aktiv || fertig ? "bg-gruen text-white" : "border border-line text-slate")
          }
        >
          {nr}
        </span>
        <div className="flex flex-col">
          <h2 className="font-display text-20 font-bold text-ink">{name}</h2>
          <p className="font-sans text-14 text-slate">
            {ROLLE[uc]}
            {vorher ? `, mit der Antwort von ${findeUc(vorher).name}` : ""}.
          </p>
        </div>
      </div>

      {station.art === "laeuft" && (
        <p className="flex items-center gap-2 font-sans text-16 text-ink">
          <span aria-hidden="true" className="size-2 rounded-full bg-gruen motion-safe:animate-pulse" />
          arbeitet, {sekunden(Math.max(0, jetzt - station.seit))} s
        </p>
      )}

      {station.art === "fehlt" && <p className="font-sans text-16 text-slate">{grundText(station.grund)} Die Kette lief ohne diese Station weiter.</p>}

      {station.art === "antwort" && <Antwort kern={station.kern} antwort={station.antwort} dauerMs={station.dauerMs} />}
    </li>
  );
}

function Antwort({ kern, antwort, dauerMs }: { kern: string; antwort: UcAntwort; dauerMs: number }) {
  const mehr = antwort.text.trim() !== kern.trim();
  return (
    <div className="flex flex-col gap-3" data-uc4-antwort="">
      <p className="font-display text-20 font-medium text-ink text-pretty">{kern}</p>
      {antwort.zahlen.length > 0 && (
        <ul className="flex flex-col gap-2">
          {antwort.zahlen.map((zahl, i) => {
            const beleg = antwort.belege[zahl.beleg];
            return (
              <li key={`${zahl.bezeichnung}-${i}`} className="flex flex-wrap items-baseline gap-x-2 gap-y-1" data-zahl="">
                <span className="font-sans text-14 text-slate">{zahl.bezeichnung}</span>
                <span className="font-sans text-16 font-semibold text-ink tabular-nums">
                  {new Intl.NumberFormat("de-AT").format(zahl.wert)}
                  {zahl.einheit ? ` ${zahl.einheit}` : ""}
                </span>
                {beleg && (
                  <HerkunftChip
                    quelle={beleg.quelle}
                    lieferung={beleg.lieferung}
                    monat={beleg.monat}
                    regelstand={beleg.regelstand}
                    sql={beleg.sql}
                    lauf={beleg.lauf}
                    verweis={beleg.ref}
                    stand={beleg.stand}
                  />
                )}
              </li>
            );
          })}
        </ul>
      )}
      {mehr && (
        <details>
          <summary className="inline-flex min-h-11 cursor-pointer items-center font-sans text-14 text-gruen underline underline-offset-4">Ganze Antwort</summary>
          <p className="mt-1 font-sans text-16 text-ink">{antwort.text}</p>
        </details>
      )}
      <ModellPille data-testid="uc4-modell">
        {antwort.modell ? (antwort.modell === "mock" ? TESTBETRIEB_TEXT : `Text: ${antwort.modell}`) : "Ohne KI, nur Code"}
        {dauerMs > 0 ? ` · ${sekunden(dauerMs)} s` : ""}
      </ModellPille>
    </div>
  );
}
