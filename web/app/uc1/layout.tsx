import type { ReactNode } from "react";
import { UcBereich } from "@kic/ui/shell";
import { LotseAnbieter } from "@/components/uc1/lotse-kontext";
import { UC1_NAVIGATION } from "@/components/uc1/navigation";

// UC1 SV KI-Lotse (#35): Unter-Navigation der Shell, darunter die Seiten. Der Anbieter hält Antworten und Sitzung
// über alle Seiten unter /uc1, damit „Leistungen“ nach dem Seitenwechsel dieselben Antworten zeigt. Die Abgrenzung
// (keine Diagnose) steht genau einmal: bei der Antwort (antworten.tsx).
export default function Uc1Layout({ children }: { children: ReactNode }) {
  return (
    <UcBereich uc="uc1" nav={UC1_NAVIGATION}>
      <LotseAnbieter>{children}</LotseAnbieter>
    </UcBereich>
  );
}
