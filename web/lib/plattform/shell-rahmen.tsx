"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { AppShell, istAktiv, zeigtHeader, type VerweisProps } from "@kic/ui/shell";
import { DemoHinweis } from "./demo-hinweis";
import { FassungsKnopf } from "./fassungs-knopf";

// Verbindet die Shell aus @kic/ui mit Next: Pfad aus usePathname, Links über next/link.
// Auf `/` und `/ablauf` (Route-Gruppe (landing)) rendert AppShell ohne Header; die Landing muss dafür nichts tun.

function NextVerweis({ href, children, ...rest }: VerweisProps) {
  return (
    <Link href={href} {...rest}>
      {children}
    </Link>
  );
}

/**
 * Woher das Abzeichen im Kopf den Modell-Zustand liest. /uc2 zeigt eine Aufzeichnung und fragt deshalb den UC2-Bereich;
 * /uc2/frage antwortet mit dem Modell der Plattform (über /api/uc4/frage), dort gilt der Standard.
 */
export function modellQuelleFuer(pfad: string): string | undefined {
  if (pfad === "/uc2/frage" || pfad.startsWith("/uc2/frage/")) return undefined;
  return pfad.startsWith("/uc2") ? "/api/uc2/modell" : undefined;
}

/** Der Hinweis zum Abbau der KI-Zugänge steht unter dem App-Kopf, nicht auf den Folien der Präsentation. */
export function zeigtDemoHinweis(pfad: string): boolean {
  return zeigtHeader(pfad) && !istAktiv("/praesentation", pfad);
}

export function ShellRahmen({ children }: { children: ReactNode }) {
  const pfad = usePathname() ?? "/";
  return (
    // UC2 liefert den Modell-Zustand selbst (Vorführmodus: mock, Badge „Testbetrieb: keine KI angeschlossen“);
    // Freigabe E0 für diese Zeile in !63.
    <AppShell
      pfad={pfad}
      Verweis={NextVerweis}
      modellQuelle={modellQuelleFuer(pfad)}
      kopfZusatz={<FassungsKnopf />}
    >
      {zeigtDemoHinweis(pfad) && <DemoHinweis />}
      {children}
    </AppShell>
  );
}
