import type { ReactNode } from "react";
import { UcBereich } from "@kic/ui/shell";

// UC2 HealthPolicy Simulator: Rahmen mit Unter-Navigation. Die statische Route `/uc2` gewinnt gegen den Fallback
// `app/[uc]`. Weitere Punkte (Abgestimmte Antwort, Quellen, Frühere Fälle) kommen mit ihren Seiten dazu.
export default function Uc2Layout({ children }: { children: ReactNode }) {
  return (
    <UcBereich
      uc="uc2"
      nav={[
        { href: "/uc2", label: "Fall stellen" },
        { href: "/uc2/panel", label: "Panel" },
      ]}
    >
      {children}
    </UcBereich>
  );
}
