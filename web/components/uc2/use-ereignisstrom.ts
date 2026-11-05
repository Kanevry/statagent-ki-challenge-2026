"use client";

import { useEffect, useRef, useState } from "react";
import { EREIGNIS_ARTEN } from "./typen";
import { LEER, wende, type FallZustand } from "./zustand";

// Hört den Ereignisstrom eines Falls (SSE) und baut daraus den Zustand. Reißt die Verbindung ab, verbindet der Browser
// sich selbst neu und schickt `Last-Event-ID`; wende() übergeht schon gesehene Nummern. Gibt der Server auf (404, 502),
// bleibt `unterbrochen`, und `neuVerbinden` startet einen neuen Versuch ab der letzten Nummer.

/** "nicht-gefunden": der Server kennt den Fall nicht (404), das ist keine abgebrochene Verbindung. */
export type Verbindung = "verbindet" | "offen" | "unterbrochen" | "zu" | "nicht-gefunden";

export function useEreignisstrom(fallId: string): {
  zustand: FallZustand;
  verbindung: Verbindung;
  neuVerbinden: () => void;
} {
  const [zustand, setZustand] = useState<FallZustand>(LEER);
  const [verbindung, setVerbindung] = useState<Verbindung>("verbindet");
  const [versuch, setVersuch] = useState(0);
  const letzte = useRef(0);

  useEffect(() => {
    if (typeof EventSource === "undefined") {
      setVerbindung("unterbrochen");
      return;
    }
    setVerbindung("verbindet");
    const ab = letzte.current > 0 ? `?seq=${letzte.current}` : "";
    const quelle = new EventSource(`/api/uc2/faelle/${encodeURIComponent(fallId)}/ereignisse${ab}`);

    quelle.onopen = () => setVerbindung("offen");
    quelle.onerror = () => {
      if (quelle.readyState !== EventSource.CLOSED) {
        setVerbindung("verbindet");
        return;
      }
      // EventSource nennt den Statuscode nicht. Kam noch nichts an, fragt ein einzelner Abruf, ob es den Fall gibt.
      if (letzte.current > 0) {
        setVerbindung("unterbrochen");
        return;
      }
      fetch(`/api/uc2/faelle/${encodeURIComponent(fallId)}`, { cache: "no-store" })
        .then((antwort) => setVerbindung(antwort.status === 404 ? "nicht-gefunden" : "unterbrochen"))
        .catch(() => setVerbindung("unterbrochen"));
    };

    const hoeren = (art: string) => (ereignis: Event) => {
      let daten: unknown;
      try {
        daten = JSON.parse((ereignis as MessageEvent<string>).data);
      } catch {
        return;
      }
      if (art === "ende") {
        setZustand((z) => wende(z, { seq: z.letzteSeq + 1, art: "ende", daten: daten ?? {} }));
        setVerbindung("zu");
        quelle.close();
        return;
      }
      const seq = (daten as { seq?: unknown } | null)?.seq;
      if (typeof seq === "number") letzte.current = Math.max(letzte.current, seq);
      setZustand((z) => wende(z, daten));
    };
    for (const art of EREIGNIS_ARTEN) quelle.addEventListener(art, hoeren(art));

    return () => quelle.close();
  }, [fallId, versuch]);

  return { zustand, verbindung, neuVerbinden: () => setVersuch((v) => v + 1) };
}
