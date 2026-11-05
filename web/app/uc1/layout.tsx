import type { ReactNode } from "react";
import { Fliesstext } from "@kic/ui/basis";
import { UcBereich } from "@kic/ui/shell";
import { LotseAnbieter } from "@/components/uc1/lotse-kontext";
import { UC1_NAVIGATION } from "@/components/uc1/navigation";

// UC1 SV KI-Lotse (#35): Unter-Navigation der Shell, darunter die Seiten. Der Anbieter hält Antworten und Sitzung
// über alle Seiten unter /uc1, damit „Erkannte Leistungen“ nach dem Seitenwechsel dieselben Antworten zeigt.
export default function Uc1Layout({ children }: { children: ReactNode }) {
  return (
    <UcBereich uc="uc1" nav={UC1_NAVIGATION}>
      <LotseAnbieter>{children}</LotseAnbieter>
      <Fliesstext groesse={12} ton="gedaempft" className="mt-auto border-t border-line pt-4">
        Keine Diagnose, keine Empfehlung für Therapie oder Medikamente.
      </Fliesstext>
    </UcBereich>
  );
}
