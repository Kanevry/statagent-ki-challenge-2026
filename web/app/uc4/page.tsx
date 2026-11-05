import type { Metadata } from "next";
import { Fliesstext, Ueberschrift } from "@kic/ui/basis";
import { UcBereich } from "@kic/ui/shell";
import { findeUc } from "@kic/ui/ucs";
import { Einstieg } from "@/components/uc4/einstieg";
import { KETTE } from "@/lib/plattform/uc4-ergebnis";

// UC4 Gemeinsamer Einstieg (#98, nicht bewertet): oben die Hauptaussage, dann das Frage-Feld, darunter die
// Karten der Kette uc3 → uc2 → uc1. Die Seite rechnet nichts; Antworten kommen über POST /api/uc4/frage.
export const metadata: Metadata = { title: `${findeUc("uc4").name} · OneShotAndy` };

export default function GemeinsamerEinstieg() {
  const namen = KETTE.map((uc) => findeUc(uc).name);
  const kette = `${namen.slice(0, -1).join(", ")} und ${namen.at(-1)}`;
  return (
    <UcBereich uc="uc4">
      <div className="flex max-w-3xl flex-col gap-2">
        <Ueberschrift stufe={2} als="h1">
          {`Eine Frage läuft nacheinander durch ${kette}.`}
        </Ueberschrift>
        <Fliesstext ton="gedaempft">
          Jeder Bereich sieht die Antworten davor. Jede Zahl zeigt, woher sie kommt.
        </Fliesstext>
      </div>
      <Einstieg />
    </UcBereich>
  );
}
