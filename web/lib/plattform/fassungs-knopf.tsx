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

/**
 * Link-Eigenschaften je Fassung. Nur der Weg zur Live-Vorführung öffnet einen neuen Tab: Wer die Passwortabfrage
 * abbricht, bleibt so auf dieser Seite (UI-Regie). Der Rückweg zur öffentlichen Fassung bleibt im selben Tab.
 */
export function fassungsLink(fassung: Fassung): {
  href: string;
  target?: "_blank";
  rel?: string;
  "data-fassung": Fassung["art"];
} {
  return fassung.art === "live"
    ? { href: fassung.adresse, target: "_blank", rel: "noopener", "data-fassung": fassung.art }
    : { href: fassung.adresse, "data-fassung": fassung.art };
}

/** Sichtbarer Text, beim neuen Tab mit einem Zusatz nur für Screenreader. */
export function FassungsInhalt({ fassung }: { fassung: Fassung }) {
  return (
    <>
      {fassungsText(fassung)}
      {fassung.art === "live" && <span className="sr-only"> (öffnet in einem neuen Tab)</span>}
    </>
  );
}

export function FassungsKnopf() {
  const fassung = useFassung();
  if (!fassung) return null;
  return (
    <a {...fassungsLink(fassung)} className={klasse}>
      <FassungsInhalt fassung={fassung} />
    </a>
  );
}
