"use client";

import { useEffect, useState } from "react";
import type { Fassung } from "./fassung";

// Weg zur anderen Fassung, im App-Kopf und auf der Startseite. Erst nach der Antwort sichtbar; ohne Adresse oder bei einem
// Fehler bleibt er weg.
const klasse =
  "inline-flex min-h-11 items-center rounded-lg px-3 py-2 font-sans text-14 text-ink underline underline-offset-4 hover:bg-paper focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy";

/** Die andere Fassung, nachdem die Route geantwortet hat; ohne Adresse oder bei einem Fehler null. */
export function useFassung(): Fassung | null {
  const [fassung, setFassung] = useState<Fassung | null>(null);

  useEffect(() => {
    let aktiv = true;
    fetch("/api/plattform/fassung", { cache: "no-store" })
      .then((antwort) => (antwort.ok ? (antwort.json() as Promise<{ fassung: Fassung | null }>) : null))
      .then((daten) => {
        if (aktiv) setFassung(daten?.fassung ?? null);
      })
      .catch(() => undefined);
    return () => {
      aktiv = false;
    };
  }, []);

  return fassung;
}

export function fassungsText(fassung: Fassung): string {
  return fassung.art === "live" ? "Live-Vorführung (mit Passwort)" : "Öffentliche Fassung";
}

export function FassungsKnopf() {
  const fassung = useFassung();
  if (!fassung) return null;
  return (
    <a href={fassung.adresse} className={klasse} data-fassung={fassung.art}>
      {fassungsText(fassung)}
    </a>
  );
}
