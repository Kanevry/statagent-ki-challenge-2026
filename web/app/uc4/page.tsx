import type { Metadata } from "next";
import { UcBereich } from "@kic/ui/shell";
import { findeUc } from "@kic/ui/ucs";
import { Kette } from "@/components/uc4/kette";
import { uc4Einstellung } from "@/lib/plattform/uc4";

// UC4 Gemeinsamer Einstieg (#98, nicht bewertet): eine Frage, die Stationen der Kette antworten nacheinander. Die
// Seite rechnet nichts; die Antworten kommen als Strom über POST /api/uc4/frage. Was online nicht geht (Kette kürzer,
// Modellwahl ohne Wirkung, Fragen zu), wird nicht angeboten.
export const metadata: Metadata = { title: `${findeUc("uc4").name} · OneShotAndy` };
export const dynamic = "force-dynamic";

export default function GemeinsamerEinstieg() {
  const { kette, fragenOffen, mitModell, modellwahl } = uc4Einstellung();
  const voll = kette.length > 1;
  return (
    <UcBereich uc="uc4">
      <div className="flex max-w-4xl flex-col gap-3 pt-4">
        <h1 className="font-display text-32 font-bold text-ink text-balance sm:text-56">
          {voll ? "Eine Frage, drei Antworten." : `Eine Frage an ${findeUc(kette[0]!).name}.`}
        </h1>
        <p className="font-sans text-20 text-slate">
          {voll
            ? "StatAgent rechnet die Zahl, der Simulator wägt ab, der Lotse sagt, was es für Sie heißt."
            : "Das Programm rechnet die Antwort aus den Daten und zeigt, woher jede Zahl kommt."}
        </p>
      </div>
      <Kette kette={kette} fragenOffen={fragenOffen} mitModell={mitModell} modellwahl={modellwahl} />
    </UcBereich>
  );
}
