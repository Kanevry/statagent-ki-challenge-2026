"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { Fliesstext, Knopf, knopfKlassen, Status, Ueberschrift } from "@kic/ui/basis";
import type { Vorbereitung } from "../../app/api/uc2/_lib/vorbereitung";
import { AKTEUR_KURZ, akteurName, datumText } from "./namen";
import { MOCK_FALL_ID, MOCK_FEHLER_ID, MERKE_FALL } from "./konstanten";
import { Schritte } from "./schritte";

// U2-0 Fall stellen (Pen bhI7X): Frage und Rahmen oben, dann die Auswahl der Akteure (höchstens 6, mit Belegzahl),
// Moderator und Experte, ein Start-Knopf. Der Blick geht von der Frage über die Auswahl zum einen grünen Knopf.

const GESPERRT = "Fragen starten ist in der Online-Demo gesperrt. Die aufgezeichnete Verhandlung lässt sich trotzdem abspielen.";

/** Rahmenwerte des Falls "wartezeiten" in Alltagssprache. Sie stehen so auch in der Frage. */
const RAHMEN = [
  { name: "Zeitraum", wert: "5 Jahre" },
  { name: "Mehrausgaben", wert: "höchstens 5 %" },
  { name: "Ziel", wert: "Wartezeit beim Facharzt um 20 % kürzer" },
];

type Zustand = { art: "bereit" } | { art: "laedt" } | { art: "fehler"; meldung: string; zumPanel?: boolean };

export function FallStellen({ vorbereitung }: { vorbereitung: Vorbereitung }) {
  const router = useRouter();
  const gruppeId = useId();
  const { fall, akteure, quelle } = vorbereitung;
  const vorschlag = akteure.filter((a) => a.vorgeschlagen).map((a) => a.akteur);
  const [gewaehlt, setGewaehlt] = useState<string[]>(vorschlag);
  const [zustand, setZustand] = useState<Zustand>({ art: "bereit" });

  const voll = gewaehlt.length >= fall.maxAkteure;
  const zuWenig = gewaehlt.length < 2;
  const weichtAb = gewaehlt.length !== vorschlag.length || gewaehlt.some((a) => !vorschlag.includes(a));
  const laedt = zustand.art === "laedt";

  function umschalten(id: string) {
    setGewaehlt((alt) => (alt.includes(id) ? alt.filter((a) => a !== id) : alt.length >= fall.maxAkteure ? alt : [...alt, id]));
  }

  async function starten() {
    if (zuWenig || laedt) return;
    setZustand({ art: "laedt" });
    let antwort: Response;
    try {
      antwort = await fetch("/api/uc2/faelle", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ fall: fall.id, akteure: gewaehlt }),
        cache: "no-store",
      });
    } catch {
      setZustand({ art: "fehler", meldung: "Keine Verbindung zum Server. Bitte versuch es gleich noch einmal." });
      return;
    }
    if (antwort.status === 403 || antwort.status === 405) {
      setZustand({ art: "fehler", meldung: GESPERRT });
      return;
    }
    if (antwort.status === 409) {
      setZustand({ art: "fehler", meldung: "Es läuft schon eine Verhandlung. Sie ist im Panel zu sehen.", zumPanel: true });
      return;
    }
    const daten: unknown = await antwort.json().catch(() => null);
    const id = daten && typeof daten === "object" && "fall_id" in daten ? String((daten as { fall_id: unknown }).fall_id) : "";
    if (!antwort.ok || !id) {
      const text = daten && typeof daten === "object" && "fehler" in daten ? String((daten as { fehler: unknown }).fehler) : "";
      const abgelehnt = "Das Panel hat die Anfrage abgelehnt. Bitte versuch es noch einmal.";
      setZustand({
        art: "fehler",
        meldung: text || (antwort.status === 422 ? abgelehnt : "Die Verhandlung konnte nicht starten. Das Panel hat nicht geantwortet."),
      });
      return;
    }
    // Hat die API die Auswahl abgelehnt, geht das als Hinweis ans Panel mit: die Seite wechselt gleich.
    const ignoriert = antwort.headers.get("x-uc2-akteure") === "ignoriert";
    try {
      sessionStorage.setItem(MERKE_FALL, id);
    } catch {
      // Ohne Speicher fehlt nur die Abkürzung über den Menüpunkt "Panel".
    }
    router.push(`/uc2/panel?fall=${encodeURIComponent(id)}${ignoriert ? "&akteure=ignoriert" : ""}`);
  }

  return (
    <>
      <div className="flex max-w-3xl flex-col gap-2">
        <Ueberschrift stufe={2} als="h1">
          Frage an das Panel
        </Ueberschrift>
        <Fliesstext ton="gedaempft">
          Sechs Gruppen aus dem Gesundheitswesen verhandeln die Frage. Ein Moderator führt durch die Runden, ein Experte
          prüft die Zahlen.
        </Fliesstext>
      </div>

      <Schritte aktiv={1} />

      {quelle === "mock" && (
        <div data-testid="uc2-mock-hinweis">
          <Status art="info">
            Der Panel-Dienst ist gerade nicht erreichbar. Es läuft die aufgezeichnete Verhandlung, ohne Sprachmodell.
          </Status>
        </div>
      )}

      <section aria-labelledby={`${gruppeId}-fall`} className="flex flex-col gap-4 border-t border-line pt-6">
        <Ueberschrift stufe={3} als="h2" id={`${gruppeId}-fall`}>
          Der Fall
        </Ueberschrift>
        <p className="max-w-4xl font-display text-20 text-ink text-balance md:text-28" data-testid="uc2-frage">
          {fall.frage}
        </p>
        <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ...RAHMEN,
            { name: "Presse bis", wert: datumText(fall.stichtag) },
          ].map((z) => (
            <div key={z.name} className="flex flex-col">
              <dt className="font-sans text-12 text-slate">{z.name}</dt>
              <dd className="font-sans text-14 font-semibold text-ink">{z.wert}</dd>
            </div>
          ))}
        </dl>
        {fall.paket && (
          <p className="max-w-4xl font-sans text-14 text-ink">
            <span className="text-slate">Geprüftes Maßnahmenpaket: </span>
            {fall.paket}
          </p>
        )}
      </section>

      <section aria-labelledby={`${gruppeId}-tisch`} className="flex flex-col gap-4 border-t border-line pt-6">
        <div className="flex flex-col gap-1">
          <Ueberschrift stufe={3} als="h2" id={`${gruppeId}-tisch`}>
            Am Tisch: bis zu sechs Gruppen
          </Ueberschrift>
          <Fliesstext groesse={14} ton="gedaempft">
            Die Zahl unter dem Namen sagt, wie viele Presseartikel zum Fall im Archiv liegen. Mehr Artikel heißt: Die Gruppe
            hat mehr zum Thema belegt gesagt.
          </Fliesstext>
          <p className="font-sans text-14 font-medium text-ink" aria-live="polite" data-testid="uc2-zaehler">
            {`${gewaehlt.length} von ${fall.maxAkteure} gewählt`}
            {voll && <span className="font-normal text-slate">. Nimm eine Gruppe heraus, um eine andere zu wählen.</span>}
          </p>
        </div>
        <ul className="grid gap-x-6 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
          {akteure.map((a) => {
            const an = gewaehlt.includes(a.akteur);
            const gesperrt = !an && voll;
            const feldId = `${gruppeId}-${a.akteur}`;
            return (
              <li key={a.akteur} className="border-t border-line first:border-t-0 sm:[&:nth-child(2)]:border-t-0 lg:[&:nth-child(3)]:border-t-0">
                <label
                  htmlFor={feldId}
                  className={`flex cursor-pointer items-start gap-3 py-3 ${gesperrt ? "cursor-not-allowed opacity-50" : ""}`}
                >
                  <input
                    id={feldId}
                    type="checkbox"
                    checked={an}
                    disabled={gesperrt}
                    onChange={() => umschalten(a.akteur)}
                    className="mt-1 size-4 shrink-0 accent-gruen"
                  />
                  <span className="flex min-w-0 flex-col">
                    <span className="font-sans text-14 font-semibold text-ink">{akteurName(a.akteur)}</span>
                    <span className="font-sans text-12 text-slate">{AKTEUR_KURZ[a.akteur] ?? ""}</span>
                    <span className="font-mono text-12 text-slate tabular-nums">
                      {a.belegzahl === 1 ? "1 Beleg" : `${a.belegzahl} Belege`}
                    </span>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
        {zuWenig && <Status art="warnung">Wähle mindestens zwei Gruppen, sonst gibt es nichts zu verhandeln.</Status>}
        {quelle === "mock" && weichtAb && (
          <Status art="info">Die aufgezeichnete Verhandlung hat immer dieselben sechs am Tisch, egal was hier gewählt ist.</Status>
        )}
      </section>

      <section className="grid gap-6 border-t border-line pt-6 md:grid-cols-2">
        <div className="flex flex-col gap-1">
          <Ueberschrift stufe={3} als="h2">
            Moderator
          </Ueberschrift>
          <Fliesstext groesse={14} ton="gedaempft">
            Führt durch die Runden, fasst zusammen und nennt offene Streitpunkte. Hat selbst keine Meinung. Immer dabei.
          </Fliesstext>
        </div>
        <div className="flex flex-col gap-1">
          <Ueberschrift stufe={3} als="h2">
            Experte für Zahlen
          </Ueberschrift>
          <Fliesstext groesse={14} ton="gedaempft">
            Rechnet die Wirkung des Maßnahmenpakets durch und zeigt, wo eine genannte Zahl nicht stimmt oder keine Quelle hat.
            Immer dabei.
          </Fliesstext>
        </div>
      </section>

      <section className="flex flex-col items-start gap-3 border-t border-line pt-6" aria-live="polite">
        <div className="flex flex-wrap items-center gap-3">
          <Knopf onClick={starten} disabled={zuWenig || laedt} data-testid="uc2-start">
            {laedt ? "Verhandlung startet" : "Verhandlung starten"}
          </Knopf>
          <Link href={`/uc2/panel?fall=${MOCK_FALL_ID}`} className={knopfKlassen("sekundaer")} data-testid="uc2-replay">
            Aufgezeichnete Verhandlung abspielen
          </Link>
        </div>
        <Fliesstext groesse={14} ton="gedaempft">
          Das Panel verhandelt höchstens 5 Runden und hört früher auf, wenn sich niemand mehr bewegt.
        </Fliesstext>
        {zustand.art === "fehler" && (
          <div className="flex flex-col items-start gap-2" role="alert">
            <Status art="fehler">{zustand.meldung}</Status>
            {zustand.zumPanel && (
              <Link href="/uc2/panel" className={knopfKlassen("sekundaer")}>
                Zum Panel
              </Link>
            )}
          </div>
        )}
        <Link href={`/uc2/panel?fall=${MOCK_FEHLER_ID}`} className="font-sans text-14 text-slate underline underline-offset-4 hover:text-ink">
          Beispiel ansehen, in dem das Modell ausfällt
        </Link>
      </section>
    </>
  );
}
