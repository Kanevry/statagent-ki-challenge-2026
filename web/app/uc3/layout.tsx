import type { ReactNode } from "react";
import { UcBereich } from "@kic/ui/shell";
import { UC3_NAVIGATION } from "@/lib/uc3/navigation";
import { DemoModus } from "./_teile/demo-modus";

// UC3 StatAgent (bewertet): fünf Punkte nach dem Persona-Panel 05.11. (Wörter aus Bewertungsbereich 6).
// Die Shell (Vertrag H, E0) zeigt die Unter-Navigation unter dem App-Header. Taste D: Demo-Ansicht.
export default function Uc3Layout({ children }: { children: ReactNode }) {
  return (
    <UcBereich uc="uc3" nav={UC3_NAVIGATION}>
      <DemoModus />
      {children}
    </UcBereich>
  );
}
