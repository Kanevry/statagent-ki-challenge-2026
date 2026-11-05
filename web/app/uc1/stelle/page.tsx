import type { Metadata } from "next";
import { StelleSeite } from "@/components/uc1/antrag-ansicht";

// /uc1/stelle, Schritt 4: die zuständige Stelle mit Fundstelle und den passenden nächsten Schritten. Keine Buchung.
export const metadata: Metadata = { title: "Stelle · KI-Lotse · OneShotAndy" };

export default function Uc1Stelle() {
  return <StelleSeite />;
}
