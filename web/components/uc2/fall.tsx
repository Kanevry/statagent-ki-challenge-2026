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

export function Fall({ vorbereitung, eigeneFrage = false }: { vorbereitung: Vorbereitung; eigeneFrage?: boolean }) {
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
      const satz = daten && typeof daten === "object" && "fehler" in daten ? (daten as { fehler: unknown }).fehler : null;
      if (antwort.status === 409) setMeldung("Es läuft schon eine Verhandlung.");
      else if (typeof satz === "string" && satz.trim() !== "") setMeldung(satz);
      else setMeldung("Die Verhandlung konnte nicht starten. Sehen Sie sich die aufgezeichnete an.");
    } catch {
      setMeldung("Keine Verbindung zum Server.");
    }
    setLaedt(false);
  }

  return (
    <div className="flex min-h-[70vh] flex-col justify-center gap-10 py-6" data-testid="uc2-fall">
      <div className="flex max-w-4xl flex-col gap-5">
        <h1 className="font-sans text-16 font-semibold text-slate">Sechs Gruppen des Gesundheitswesens verhandeln über Wartezeiten beim Facharzt.</h1>
        <p lang="de" className="font-display text-32 font-bold break-words text-ink text-balance hyphens-auto sm:text-56">{fall.frage}</p>
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
        {eigeneFrage && (
          <Link href="/uc2/frage" className="inline-flex min-h-11 items-center font-sans text-14 text-gruen underline underline-offset-4">
            Eigene Frage ausprobieren
          </Link>
        )}
        {modus === "live" && (
          <button type="button" onClick={neuVerhandeln} disabled={laedt} className="min-h-11 font-sans text-14 text-gruen underline underline-offset-4 disabled:opacity-50">
            {laedt ? "Startet, das kann eine halbe Minute dauern …" : "Neu verhandeln lassen, mit Modell"}
          </button>
        )}
      </div>
      {modus === "live" && (
        <p className="-mt-6 font-sans text-14 text-slate">Eine neue Verhandlung dauert rund fünf Minuten. Die Runden erscheinen, sobald sie fertig sind.</p>
      )}
      {meldung && (
        <p role="status" className="font-sans text-14 text-ink">
          {meldung}
        </p>
      )}
    </div>
  );
}
