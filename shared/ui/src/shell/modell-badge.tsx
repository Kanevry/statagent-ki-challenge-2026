"use client";

import { useEffect, useState } from "react";
import { Status } from "../basis/status";
import { modellStatusSchema, type ModellStatus } from "./modell-status";

// Modell-Badge (Pen-Frame CKCV4): zeigt, welches Sprachmodell gerade antwortet, als `provider · modell`.
// Die 2-px-Linie in Violett markiert KI (Token-Regel), der Wert steht in Mono, weil er ein Datum ist.

type Zustand = { art: "laden" } | { art: "ok"; status: ModellStatus } | { art: "fehler" };

export function ModellBadge({ quelle = "/api/plattform/modell" }: { quelle?: string }) {
  const [zustand, setZustand] = useState<Zustand>({ art: "laden" });

  useEffect(() => {
    const abbruch = new AbortController();
    fetch(quelle, { signal: abbruch.signal, cache: "no-store" })
      .then(async (antwort) => {
        const geprueft = modellStatusSchema.safeParse(await antwort.json());
        if (!antwort.ok || !geprueft.success || geprueft.data.provider === "unbekannt") {
          setZustand({ art: "fehler" });
          return;
        }
        setZustand({ art: "ok", status: geprueft.data });
      })
      .catch(() => {
        if (!abbruch.signal.aborted) setZustand({ art: "fehler" });
      });
    return () => abbruch.abort();
  }, [quelle]);

  if (zustand.art === "fehler") {
    return (
      <Status art="warnung" data-testid="modell-badge">
        Modell nicht erreichbar
      </Status>
    );
  }

  const wert = zustand.art === "ok" ? `${zustand.status.provider} · ${zustand.status.modell}` : "wird geprüft";
  const titel =
    zustand.art === "ok"
      ? [zustand.status.version && `Version ${zustand.status.version}`, `Quelle: ${zustand.status.quelle}`]
          .filter(Boolean)
          .join(", ")
      : undefined;

  return (
    <p
      className="inline-flex h-8 items-center gap-2 border-l-2 border-violett pl-2 font-sans text-12"
      aria-live="polite"
      title={titel}
      data-testid="modell-badge"
    >
      <span className="text-slate">Modell</span>
      <span className={zustand.art === "ok" ? "font-mono text-ink" : "text-slate"}>{wert}</span>
    </p>
  );
}
