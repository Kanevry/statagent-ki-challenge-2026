"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Fliesstext, Knopf, Status } from "@kic/ui/basis";
import { ergebnisSchema, MAX_FRAGE, type Ergebnis } from "../../lib/plattform/uc4-ergebnis";
import { kuerzel } from "./buehne/takt";
import { gliedere, OHNE_ARTIKEL } from "./eigene-frage-text";
import { akteurName } from "./namen";

// /uc2/frage: Feld, eine Hauptaktion, Antwort. Fragt nur die Station UC2 über /api/uc4/frage (Schutz siehe Route).

export const KENNZEICHNUNG = "Prototyp, KI-Antwort, ohne Gewähr.";
export const BEISPIELE = [
  "Sollen Apotheken in Österreich impfen dürfen?",
  "Soll es am Land mehr Kassenstellen geben?",
  "Sollen Gesundheitsleistungen stärker aus Steuern bezahlt werden?",
] as const;
const AM_TISCH = ["aerztekammer", "patienten", "sv"] as const;
const NICHT_ABGEWOGEN = "Diese Frage konnte gerade nicht abgewogen werden. Bitte formulieren Sie sie anders oder versuchen Sie es später noch einmal.";

type Lage =
  | { art: "leer" }
  | { art: "laden" }
  | { art: "fehler"; meldung: string }
  | { art: "absage"; meldung: string }
  | { art: "antwort"; frage: string; antwort: Ergebnis["antworten"][number] };

async function stelleFrage(frage: string): Promise<Lage> {
  try {
    const antwort = await fetch("/api/uc4/frage?station=uc2", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ frage }),
      cache: "no-store",
    });
    const daten: unknown = await antwort.json().catch(() => null);
    if (!antwort.ok) {
      const meldung = daten && typeof daten === "object" && "fehler" in daten ? String((daten as { fehler: unknown }).fehler) : NICHT_ABGEWOGEN;
      return { art: "fehler", meldung };
    }
    const ergebnis = ergebnisSchema.safeParse(daten);
    const station = ergebnis.success ? ergebnis.data.antworten.find((a) => a.uc === "uc2") : undefined;
    if (!station) return { art: "fehler", meldung: NICHT_ABGEWOGEN };
    // Ohne Modell: fester Satz des Servers (nicht zum Thema, persönliche Angaben), keine KI-Antwort.
    return station.modell === null ? { art: "absage", meldung: station.text } : { art: "antwort", frage, antwort: station };
  } catch {
    return { art: "fehler", meldung: "Keine Verbindung zum Server." };
  }
}

function Antwort({ frage, text }: { frage: string; text: string }) {
  const { themen, stimmen, bedingungen, rest } = gliedere(text);
  const bereich = useRef<HTMLElement>(null);
  // Am Handy steht die Antwort sonst unter dem Formular. Ohne „smooth“, also auch ohne Bewegung bei reduced-motion.
  useEffect(() => {
    bereich.current?.scrollIntoView({ block: "start" });
  }, [text]);
  return (
    <section ref={bereich} aria-labelledby="uc2-antwort-titel" className="flex max-w-3xl flex-col gap-6 border-t border-line pt-6" data-testid="uc2-eigene-antwort">
      <div className="flex flex-col gap-2">
        <p className="font-sans text-14 font-semibold text-slate">{KENNZEICHNUNG}</p>
        <h2 id="uc2-antwort-titel" className="font-display text-24 font-bold text-ink text-balance">
          {frage}
        </h2>
      </div>
      {themen.length > 0 && (
        <ul aria-label="Stand je Thema" className="flex flex-col gap-3">
          {themen.map(({ thema, stand }) => (
            <li key={thema} className="flex items-start gap-3 font-sans text-16 text-ink">
              <span aria-hidden="true" className={`mt-1.5 size-3 shrink-0 rounded-full ${stand === "alle dafür" ? "bg-gruen" : stand === "noch strittig" ? "border-2 border-slate" : "bg-slate"}`} />
              <span>
                {thema}: <span className="font-semibold">{stand}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
      {stimmen.length > 0 && (
        <ul className="flex flex-col border-t border-line">
          {stimmen.map((stimme) => (
            <li key={stimme.name} className="flex flex-col gap-1 border-b border-line py-4">
              <h3 className="font-sans text-16 font-semibold text-ink">{stimme.name}</h3>
              {stimme.haltung && <p className="font-sans text-14 text-slate">{stimme.haltung}</p>}
              {stimme.grund && <p className="font-sans text-16 text-ink">{stimme.grund}</p>}
              {stimme.beleg && <p className="font-sans text-12 text-slate">Quelle: {stimme.beleg}</p>}
              {stimme.ohneArtikel && <p className="font-sans text-12 text-slate">{OHNE_ARTIKEL}</p>}
            </li>
          ))}
        </ul>
      )}
      {bedingungen.length > 0 && (
        <details className="font-sans text-14 text-ink">
          <summary className="min-h-11 cursor-pointer py-3 font-semibold">Unter welchen Bedingungen ({bedingungen.length})</summary>
          <ul className="flex list-disc flex-col gap-1 pl-5">
            {bedingungen.map((bedingung) => (
              <li key={bedingung}>{bedingung}</li>
            ))}
          </ul>
        </details>
      )}
      {rest.map((zeile) => (
        <Fliesstext key={zeile} groesse={12} ton="gedaempft">
          {zeile}
        </Fliesstext>
      ))}
    </section>
  );
}

export function EigeneFrage() {
  const [frage, setFrage] = useState("");
  const [lage, setLage] = useState<Lage>({ art: "leer" });
  const laedt = lage.art === "laden";
  const ansage = laedt ? "Die Frage wird abgewogen." : lage.art === "antwort" ? "Die Antwort steht jetzt unter dem Formular." : lage.art === "absage" ? lage.meldung : "";

  async function absenden(ereignis: FormEvent<HTMLFormElement>) {
    ereignis.preventDefault();
    const text = frage.trim();
    if (laedt) return;
    if (!text) {
      setLage({ art: "fehler", meldung: "Bitte eine Frage eingeben." });
      return;
    }
    setLage({ art: "laden" });
    setLage(await stelleFrage(text));
  }

  return (
    <div className="flex flex-col gap-8 py-6" data-testid="uc2-eigene-frage">
      <div className="flex max-w-3xl flex-col gap-3">
        <p className="font-sans text-14 font-semibold text-slate">{KENNZEICHNUNG}</p>
        <h1 className="font-display text-32 font-bold text-ink text-balance">Stellen Sie Ihre eigene Frage zur Gesundheitspolitik.</h1>
        <Fliesstext>Drei Interessenvertretungen wägen sie ab. Ihre Rollen spielt eine KI. Es ist keine echte Verhandlung und keine Aussage dieser Organisationen.</Fliesstext>
      </div>

      <form onSubmit={(e) => void absenden(e)} noValidate aria-busy={laedt} className="flex max-w-3xl flex-col gap-4">
        <div className="flex flex-col gap-2">
          <label htmlFor="uc2-frage" className="font-sans text-14 font-semibold text-ink">
            Ihre Frage
          </label>
          <textarea
            id="uc2-frage"
            rows={3}
            maxLength={MAX_FRAGE}
            value={frage}
            onChange={(e) => setFrage(e.target.value)}
            aria-describedby="uc2-frage-hinweis"
            placeholder={`Zum Beispiel: ${BEISPIELE[0]}`}
            className="w-full resize-y rounded border border-slate bg-white p-4 font-sans text-16 text-ink placeholder:text-slate focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen"
          />
          <p id="uc2-frage-hinweis" className="font-sans text-12 text-slate">
            {`Bitte keine persönlichen Daten eingeben. Höchstens ${MAX_FRAGE} Zeichen.`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-6">
          <Knopf type="submit" aria-disabled={laedt} className="min-h-11 aria-disabled:cursor-not-allowed aria-disabled:opacity-50">
            {laedt ? "Wird abgewogen" : "Abwägen lassen"}
          </Knopf>
          <Link href="/uc2" className="inline-flex min-h-11 items-center font-sans text-14 text-gruen underline underline-offset-4">
            Zurück zur aufgezeichneten Verhandlung
          </Link>
        </div>
        {lage.art === "leer" && (
          <>
            <p id="uc2-beispiele" className="font-sans text-14 font-semibold text-ink">
              Beispiele
            </p>
            <ul aria-labelledby="uc2-beispiele" className="flex flex-col border-t border-line">
              {BEISPIELE.map((satz) => (
                <li key={satz} className="border-b border-line">
                  <button type="button" onClick={() => setFrage(satz)} className="min-h-11 w-full py-3 text-left font-sans text-14 text-ink hover:text-gruen focus-visible:outline-2 focus-visible:outline-gruen">
                    {satz}
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </form>

      {/* Bleibt immer im Baum: Screenreader sagen nur Änderungen in einer schon vorhandenen Region an. */}
      <p role="status" className="sr-only">
        {ansage}
      </p>
      {laedt && (
        <div className="flex max-w-3xl flex-col gap-3" data-testid="uc2-eigene-laden">
          <ul aria-hidden="true" className="flex gap-3">
            {AM_TISCH.map((a, i) => (
              <li key={a} style={{ animationDelay: `${i * 300}ms` }} className="flex h-10 w-10 items-center justify-center rounded-full border border-line bg-white font-sans text-12 font-semibold text-slate motion-safe:animate-pulse">
                {kuerzel(a)}
              </li>
            ))}
          </ul>
          <Fliesstext>{`${AM_TISCH.map(akteurName).join(", ")} wägen ab. Das dauert meist unter einer Minute.`}</Fliesstext>
        </div>
      )}
      {lage.art === "fehler" && <Status art="fehler" role="alert">{lage.meldung}</Status>}
      {lage.art === "absage" && (
        <p className="max-w-3xl border-t border-line pt-6 font-sans text-16 text-ink" data-testid="uc2-eigene-absage">
          {lage.meldung}
        </p>
      )}
      {lage.art === "antwort" && <Antwort frage={lage.frage} text={lage.antwort.text} />}
    </div>
  );
}
