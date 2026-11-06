"use client";

import { useEffect, useState } from "react";
import type { Fassung } from "./fassung";

// Knopf im Kopf zur anderen Fassung. Erst nach der Antwort sichtbar; ohne Adresse oder bei einem Fehler bleibt er weg.
const klasse =
  "inline-flex min-h-11 items-center rounded-lg px-3 py-2 font-sans text-14 text-ink underline underline-offset-4 hover:bg-paper focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy";

export function FassungsKnopf() {
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

  if (!fassung) return null;
  return (
    <a href={fassung.adresse} className={klasse} data-fassung={fassung.art}>
      {fassung.art === "live" ? "Live-Vorführung (mit Passwort)" : "Öffentliche Fassung"}
    </a>
  );
}
