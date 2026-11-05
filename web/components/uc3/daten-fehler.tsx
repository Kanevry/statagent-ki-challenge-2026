"use client";

import { knopfKlassen, Ueberschrift } from "@kic/ui/basis";
import type { Lesung } from "./db";

// Fehlerzustand, wenn die UC3-Datenbank nicht antwortet (UI-Regie v1): getrennt vom Leerzustand „Noch kein Monat
// ist gerechnet.“, damit die Seite nicht behauptet, es gebe keine Zahlen. Mittig in der Fläche, ein Satz, ein Knopf.

type Grund = Exclude<Lesung<unknown>, { ok: true }>["grund"];

const TEXT: Record<"keine-datenbank" | "sonst", { titel: string; satz: string }> = {
  "keine-datenbank": {
    titel: "Hier ist keine Datenbank angeschlossen.",
    satz: "Die Zahlen erscheinen, sobald die UC3-Datenbank läuft.",
  },
  sonst: {
    titel: "Die Zahlen sind gerade nicht erreichbar.",
    satz: "Es wurde nichts geändert. Laden Sie die Seite in einer Minute neu.",
  },
};

export function DatenFehler({ grund }: { grund: Grund }) {
  const t = grund === "keine-datenbank" ? TEXT["keine-datenbank"] : TEXT.sonst;
  return (
    <section
      role="alert"
      aria-labelledby="daten-fehler-titel"
      className="flex min-h-[50vh] flex-col items-center justify-center gap-4 text-center"
      data-zustand="daten-fehler"
    >
      <Ueberschrift stufe={2} als="h1" id="daten-fehler-titel">
        {t.titel}
      </Ueberschrift>
      <p className="max-w-md font-sans text-16 text-slate">{t.satz}</p>
      {grund !== "keine-datenbank" && (
        <button type="button" onClick={() => window.location.reload()} className={knopfKlassen("primaer")}>
          Neu laden
        </button>
      )}
    </section>
  );
}
