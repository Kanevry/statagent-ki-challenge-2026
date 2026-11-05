"use client";

import { useEffect } from "react";
import { useShell } from "./kontext";

/**
 * Meldet dem Modell-Badge im Header, womit diese Seite rechnet, zum Beispiel `provider="mock"`, wenn die Seite im
 * Testbetrieb läuft, während die App global auf azure steht. Ohne diese Angabe zeigt der Badge die globale
 * Einstellung (`plattform.llm status`). Rendert nichts; beim Verlassen der Seite gilt wieder die globale Angabe.
 */
export function SeitenModell({ provider, modell = null }: { provider: string; modell?: string | null }) {
  const { setzeSeitenModell } = useShell();
  useEffect(() => {
    setzeSeitenModell({ provider, modell });
    return () => setzeSeitenModell(null);
  }, [provider, modell, setzeSeitenModell]);
  return null;
}
