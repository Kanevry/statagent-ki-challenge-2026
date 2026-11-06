import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ShellRahmen } from "@/lib/plattform/shell-rahmen";
import "./globals.css";

export const metadata: Metadata = {
  title: "OneShotAndy · KI Challenge 2026",
  description: "StatAgent, SV KI-Lotse und HealthPolicy Simulator auf einer gemeinsamen Plattform",
  // Dasselbe Icon wie die Startseite, damit auch jede App-Seite eines hat. Für die Anfrage, die Browser von sich aus
  // stellen, liegt dasselbe Zeichen als public/favicon.ico bereit (#206).
  icons: { icon: { url: "/landing/favicon.svg", type: "image/svg+xml" } },
};

// Root-Layout: ShellRahmen setzt Header, Modell-Badge und Protokoll-Schublade (#57) überall außer auf `/`.
// Die Landing (Route-Gruppe (landing), `/`) rendert frei und muss dafür nichts tun.
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="de">
      <body className="flex min-h-dvh flex-col bg-paper font-sans text-ink antialiased">
        <ShellRahmen>{children}</ShellRahmen>
      </body>
    </html>
  );
}
