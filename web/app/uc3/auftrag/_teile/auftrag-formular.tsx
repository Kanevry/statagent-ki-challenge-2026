"use client";

import Link from "next/link";
import { useCallback, useEffect, useId, useState, type FormEvent } from "react";
import { Knopf, Status, Ueberschrift } from "@kic/ui/basis";
import { formatZahl } from "@kic/ui/bausteine";
import type { AuftragStand } from "@/components/uc3/auftrag";
import { monatName } from "@/components/uc3/monat";
import { laufPfad } from "@/components/uc3/navigation";

// Eine Hauptaktion: Satz tippen, der Agent rechnet, dann weiter zur Freigabe. Der Stand kommt per Abfrage, damit ein
// schwaches Netz den Lauf nicht abreißt; eine ausgefallene Abfrage wird still wiederholt und nur benannt.

const ABFRAGE_MS = 3000;
const textLink =
  "inline-flex min-h-11 items-center font-sans text-16 font-medium text-gruen underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy";
const fokus = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy";

function sekunden(stand: AuftragStand, jetzt: number): number {
  const ende = stand.endeAm ? new Date(stand.endeAm).getTime() : jetzt;
  return Math.max(0, Math.round((ende - new Date(stand.gestartetAm).getTime()) / 1000));
}

function dauerText(s: number): string {
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
}

function Ergebnis({ stand, jetzt }: { stand: AuftragStand; jetzt: number }) {
  const dauer = dauerText(sekunden(stand, jetzt));
  if (stand.zustand === "laeuft") {
    return (
      <p role="status" className="font-sans text-16 text-ink">
        {stand.art === "agent"
          ? `Die Agenten arbeiten und rechnen die Zahlen nach, seit ${dauer}. Das kann einige Minuten dauern.`
          : `${monatName(stand.text)} wird gerechnet, seit ${dauer}.`}
      </p>
    );
  }
  if (stand.zustand === "vorschlag") {
    return (
      <div role="status" className="flex flex-col gap-2">
        <p className="font-sans text-16 text-ink">Der Vorschlag liegt bereit, nach {dauer}. Noch ist nichts geändert.</p>
        {stand.satz && <p className="font-sans text-14 text-slate">({stand.satz})</p>}
        <Link href={`/uc3/freigaben/${stand.vorschlagId}`} className={textLink}>
          Vorher und nachher ansehen, dann entscheiden
        </Link>
      </div>
    );
  }
  if (stand.zustand === "gerechnet") {
    return (
      <div role="status" className="flex flex-col gap-2">
        <p className="font-sans text-16 text-ink">
          {monatName(stand.text)} gerechnet
          {stand.gezaehlt !== null ? `: ${formatZahl(stand.gezaehlt)} Beschäftigungsverhältnisse` : ""}, in {dauer}.
        </p>
        <Link href={laufPfad(stand.text, stand.regelsatz ?? "v1")} className={textLink}>
          Monat und Qualitätsbericht ansehen
        </Link>
      </div>
    );
  }
  if (stand.zustand === "rueckfrage") {
    return (
      <p role="status" className="font-sans text-16 text-ink">
        Die Agenten fragen zurück: {stand.satz}
      </p>
    );
  }
  return (
    <Status art="fehler">
      {stand.zustand === "abgelehnt" ? `Kein Vorschlag: ${stand.satz}` : (stand.satz ?? "Das hat nicht geklappt.")}
    </Status>
  );
}

export function AuftragFormular({
  monate,
  probeMonate,
  rechenbar,
  regelsatz,
}: {
  monate: readonly string[];
  probeMonate: readonly string[];
  rechenbar: readonly string[];
  regelsatz: string;
}) {
  const [satz, setSatz] = useState("");
  const [monat, setMonat] = useState(rechenbar.includes("2025-10") ? "2025-10" : (rechenbar[0] ?? ""));
  const [probe, setProbe] = useState("");
  const [stand, setStand] = useState<AuftragStand | null>(null);
  const [meldung, setMeldung] = useState<string | null>(null);
  const [netzWeg, setNetzWeg] = useState(false);
  const [jetzt, setJetzt] = useState(() => Date.now());
  const satzId = useId();
  const monatId = useId();
  const probeId = useId();
  const laeuft = stand?.zustand === "laeuft";

  const abfragen = useCallback(async () => {
    try {
      const antwort = await fetch("/api/uc3/auftrag", { cache: "no-store" });
      if (!antwort.ok) throw new Error(String(antwort.status));
      const daten = (await antwort.json()) as { stand: AuftragStand | null };
      setStand(daten.stand);
      setNetzWeg(false);
    } catch {
      setNetzWeg(true);
    }
  }, []);

  // Beim Öffnen den letzten Stand holen: so findet auch ein Neuladen den laufenden Auftrag wieder.
  useEffect(() => {
    void abfragen();
  }, [abfragen]);

  useEffect(() => {
    // Auch wenn schon die erste Abfrage scheiterte: Sonst bliebe die Seite ohne Stand und fragte nie wieder.
    if (!laeuft && !netzWeg) return;
    const abfrage = setInterval(() => void abfragen(), ABFRAGE_MS);
    const uhr = laeuft ? setInterval(() => setJetzt(Date.now()), 1000) : undefined;
    return () => {
      clearInterval(abfrage);
      clearInterval(uhr);
    };
  }, [laeuft, netzWeg, abfragen]);

  async function starten(body: Record<string, string>) {
    setMeldung(null);
    try {
      const antwort = await fetch("/api/uc3/auftrag", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      const daten = (await antwort.json().catch(() => ({}))) as { stand?: AuftragStand; fehler?: string };
      if (daten.stand) setStand(daten.stand);
      setJetzt(Date.now());
      if (!antwort.ok) setMeldung(daten.fehler ?? "Das hat nicht geklappt. Bitte noch einmal versuchen.");
    } catch {
      setMeldung("Der Server ist gerade nicht erreichbar. Bitte noch einmal versuchen.");
    }
  }

  function auftragSenden(e: FormEvent) {
    e.preventDefault();
    if (!satz.trim()) {
      setMeldung("Bitte schreiben Sie den Auftrag in einem Satz.");
      return;
    }
    void starten({ art: "agent", anweisung: satz, probe });
  }

  return (
    <div className="flex max-w-3xl flex-col gap-8">
      <header className="flex flex-col gap-3">
        <Ueberschrift stufe={2} als="h1">
          Änderung in einem Satz
        </Ueberschrift>
        <p className="font-sans text-16 text-slate">
          Die Agenten schreiben daraus einen Vorschlag mit den Zahlen vorher und nachher. Wirksam wird er erst, wenn ein
          Mensch ihn mit Namen freigibt.
        </p>
      </header>

      <form onSubmit={auftragSenden} className="flex flex-col gap-3">
        <label htmlFor={satzId} className="font-sans text-14 font-semibold text-ink">
          Auftrag
        </label>
        <textarea
          id={satzId}
          rows={3}
          maxLength={1000}
          value={satz}
          onChange={(e) => setSatz(e.target.value)}
          className={`rounded border border-slate bg-white px-4 py-2 font-sans text-16 text-ink ${fokus}`}
        />
        {monate.length > 0 && (
          <div className="flex flex-col gap-2">
            <label htmlFor={probeId} className="font-sans text-14 font-semibold text-ink">
              Zahlen vorher und nachher für
            </label>
            <select
              id={probeId}
              value={probe}
              onChange={(e) => setProbe(e.target.value)}
              className={`h-10 w-fit rounded border border-slate bg-white px-4 font-sans text-16 text-ink ${fokus}`}
            >
              <option value="">{`${monatName(monate[0]!)} (jüngster Monat)`}</option>
              {probeMonate.filter((m) => m !== monate[0]).map((m) => (
                <option key={m} value={m}>
                  {monatName(m)}
                </option>
              ))}
            </select>
          </div>
        )}
        <div>
          <Knopf type="submit" disabled={laeuft}>
            Vorschlag schreiben lassen
          </Knopf>
        </div>
      </form>

      {meldung && <Status art="fehler">{meldung}</Status>}
      {netzWeg && (
        <p className="font-sans text-14 text-slate">
          {laeuft ? "Die Verbindung ist kurz weg. Der Auftrag läuft weiter." : "Die Verbindung ist kurz weg. Die Seite versucht es weiter."}
        </p>
      )}
      {stand && (
        <section aria-label="Stand des Auftrags" className="flex flex-col gap-2 border-t border-line pt-4">
          {stand.art === "agent" && <p className="font-sans text-14 text-slate">Auftrag: {stand.text}</p>}
          <Ergebnis stand={stand} jetzt={jetzt} />
        </section>
      )}

      {rechenbar.length > 0 && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void starten({ art: "lauf", lieferung: monat, regelsatz });
          }}
          className="flex flex-col gap-3 border-t border-line pt-6"
        >
          <label htmlFor={monatId} className="font-sans text-14 font-semibold text-ink">
            {`Einen Monat rechnen, mit dem aktuellen Regelsatz ${regelsatz}`}
          </label>
          <div className="flex flex-wrap items-center gap-3">
            <select
              id={monatId}
              value={monat}
              onChange={(e) => setMonat(e.target.value)}
              className={`h-10 rounded border border-slate bg-white px-4 font-sans text-16 text-ink ${fokus}`}
            >
              {rechenbar.map((m) => (
                <option key={m} value={m}>
                  {monatName(m)}
                </option>
              ))}
            </select>
            <Knopf type="submit" art="sekundaer" disabled={laeuft}>
              Rechnen
            </Knopf>
          </div>
        </form>
      )}
    </div>
  );
}
