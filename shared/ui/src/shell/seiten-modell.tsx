"use client";

import { useEffect } from "react";
import { useShell } from "./kontext";

/**
 * Meldet dem Modell-Badge im Header, womit diese Seite rechnet, zum Beispiel `provider="mock"`, wenn die Seite im
 * Testbetrieb läuft, während die App global auf azure steht. Ohne diese Angabe zeigt der Badge die globale
 * Einstellung (`plattform.llm status`). Rendert nichts; beim Verlassen der Seite gilt wieder die globale Angabe.
 * `aufzeichnung` meldet, dass die Seite gerade aufgezeichnete Inhalte zeigt (`<SeitenModell aufzeichnung />`);
 * der Anbieter spielt dann keine Rolle.
 */
export function SeitenModell({
  provider = "",
  modell = null,
  gewaehlt = false,
  aufzeichnung = false,
}: {
  provider?: string;
  modell?: string | null;
  /** Nur setzen, wenn die Seite den Anbieter wirklich mit ihren Anfragen schickt (Modellwahl). */
  gewaehlt?: boolean;
  /** Nur setzen, solange der gezeigte Inhalt wirklich aufgezeichnet ist, nie neben einer Live-Antwort. */
  aufzeichnung?: boolean;
}) {
  const { setzeSeitenModell } = useShell();
  useEffect(() => {
    setzeSeitenModell({ provider, modell, gewaehlt, aufzeichnung });
    return () => setzeSeitenModell(null);
  }, [provider, modell, gewaehlt, aufzeichnung, setzeSeitenModell]);
  return null;
}
