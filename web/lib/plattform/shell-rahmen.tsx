"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { AppShell, type VerweisProps } from "@kic/ui/shell";

// Verbindet die Shell aus @kic/ui mit Next: Pfad aus usePathname, Links über next/link.
// Auf `/` (Landing, Route-Gruppe (landing)) rendert AppShell ohne Header; die Landing muss dafür nichts tun.

function NextVerweis({ href, children, ...rest }: VerweisProps) {
  return (
    <Link href={href} {...rest}>
      {children}
    </Link>
  );
}

export function ShellRahmen({ children }: { children: ReactNode }) {
  const pfad = usePathname() ?? "/";
  return (
    // UC2 liefert den Modell-Zustand selbst (Vorführmodus: mock, Badge „Testbetrieb: keine KI angeschlossen“);
    // Freigabe E0 b-e0-34 für diese Zeile in !63.
    <AppShell
      pfad={pfad}
      Verweis={NextVerweis}
      modellQuelle={pfad.startsWith("/uc2") ? "/api/uc2/modell" : undefined}
    >
      {children}
    </AppShell>
  );
}
