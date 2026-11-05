"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { knopfKlassen } from "@kic/ui/basis";
import type { Vorbereitung } from "../../app/api/uc2/_lib/vorbereitung";
import { akteurName } from "./namen";
import { MOCK_FALL_ID } from "./konstanten";
import { kuerzel } from "./buehne/takt";

// /uc2: die Frage, wer am Tisch sitzt, eine Hauptaktion. Die aufgezeichnete Verhandlung ist die Vorführung. Eine
// neue Verhandlung mit Modell gibt es nur, wenn die Python-API erreichbar ist (lokal); online wird sie nicht angeboten.

export function Fall({ vorbereitung }: { vorbereitung: Vorbereitung }) {
  const router = useRouter();
  const { fall, akteure, modus } = vorbereitung;
  const amTisch = akteure.filter((a) => a.vorgeschlagen).map((a) => a.akteur);
  const [laedt, setLaedt] = useState(false);
  const [meldung, setMeldung] = useState<string | null>(null);

  async function neuVerhandeln() {
    setLaedt(true);
    setMeldung(null);
    try {
      const antwort = await fetch("/api/uc2/faelle", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ fall: fall.id, akteure: amTisch }),
        cache: "no-store",
      });
      const daten: unknown = await antwort.json().catch(() => null);
      const id = daten && typeof daten === "object" && "fall_id" in daten ? String((daten as { fall_id: unknown }).fall_id) : "";
      if (antwort.ok && id) {
        router.push(`/uc2/panel?fall=${encodeURIComponent(id)}`);
        return;
      }
      setMeldung(antwort.status === 409 ? "Es läuft schon eine Verhandlung." : "Die Verhandlung konnte nicht starten. Sehen Sie sich die aufgezeichnete an.");
    } catch {
      setMeldung("Keine Verbindung zum Server.");
    }
    setLaedt(false);
  }

  return (
    <div className="flex min-h-[70vh] flex-col justify-center gap-10 py-6" data-testid="uc2-fall">
      <div className="flex max-w-4xl flex-col gap-5">
        <p className="font-sans text-16 text-slate">Ein Panel aus sechs Gruppen des Gesundheitswesens verhandelt eine Frage.</p>
        <h1 className="font-display text-56 font-bold text-ink text-balance">{fall.frage}</h1>
        <p className="font-sans text-16 text-slate">Geprüft wird das Paket: {fall.paket}.</p>
      </div>

      <section aria-labelledby="tisch-titel" className="flex flex-col gap-4">
        <h2 id="tisch-titel" className="font-sans text-14 font-semibold text-ink">
          Am Tisch
        </h2>
        <ul className="flex flex-wrap gap-x-8 gap-y-3">
          {amTisch.map((a) => (
            <li key={a} className="flex items-center gap-2 font-sans text-16 text-ink">
              <span aria-hidden="true" className="flex h-[26px] w-[26px] items-center justify-center rounded-full border border-line bg-white font-sans text-11 font-semibold text-slate">
                {kuerzel(a)}
              </span>
              {akteurName(a)}
            </li>
          ))}
        </ul>
        <p className="font-sans text-14 text-slate">Ein Moderator führt durch die Runden. Ein Experte rechnet die Zahlen ohne KI nach.</p>
      </section>

      <div className="flex flex-wrap items-center gap-6">
        <Link href={`/uc2/panel?fall=${MOCK_FALL_ID}`} className={knopfKlassen("primaer", "h-14 px-6 text-16")}>
          Verhandlung ansehen
        </Link>
        {modus === "live" && (
          <button type="button" onClick={neuVerhandeln} disabled={laedt} className="min-h-11 font-sans text-14 text-gruen underline underline-offset-4 disabled:opacity-50">
            {laedt ? "Startet …" : "Neu verhandeln lassen, mit Modell"}
          </button>
        )}
      </div>
      {meldung && (
        <p role="status" className="font-sans text-14 text-ink">
          {meldung}
        </p>
      )}
    </div>
  );
}
