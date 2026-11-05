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
    <AppShell pfad={pfad} Verweis={NextVerweis}>
      {children}
    </AppShell>
  );
}
