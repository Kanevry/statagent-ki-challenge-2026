import type { ReactNode } from "react";
import { UcBereich } from "@kic/ui/shell";
import { LotseAnbieter } from "@/components/uc1/lotse-kontext";

// UC1 SV KI-Lotse (#35): keine Tab-Leiste (Urteil der Sichtprüfung), die Führung trägt der Schrittzeiger mit drei Schritten.
// Der Anbieter hält Antworten und Sitzung über alle Seiten unter /uc1, damit „Leistungen“ und „Antrag“ nach dem
// Seitenwechsel dieselben Antworten zeigen. Die Abgrenzung (keine Diagnose) steht genau einmal: bei der Antwort.
export default function Uc1Layout({ children }: { children: ReactNode }) {
  return (
    <UcBereich uc="uc1">
      <LotseAnbieter>{children}</LotseAnbieter>
    </UcBereich>
  );
}
