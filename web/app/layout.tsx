import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "OneShotAndy · KI Challenge 2026",
  description: "StatAgent, SV KI-Lotse und HealthPolicy Simulator auf einer gemeinsamen Plattform",
};

// Root-Layout ohne App-Header: die Route-Gruppe (landing) rendert frei (Session b-landing, `/`).
// Die Shell mit Header, Modell-Badge und Protokoll-Schublade für /uc1 /uc2 /uc3 /praesentation kommt mit #57.
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}
