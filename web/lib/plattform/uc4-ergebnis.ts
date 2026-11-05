import { ucAntwortSchema } from "@kic/ui/antwortform";
import { z } from "zod";

// Vertrag der UC4-Kette für Route und Seite (#98): `plattform.router.Ergebnis` als zod-Schema. Die Antworten
// prüft `ucAntwortSchema` aus @kic/ui/antwortform (#96), hier kommt nur die Hülle dazu. Ohne Node-Importe,
// damit die Client-Komponente dasselbe Schema nutzt wie der Route-Handler.

/** Reihenfolge der Kette (`plattform.router.STANDARD_KETTE`): jeder Schritt sieht die Antworten davor. */
export const KETTE = ["uc3", "uc2", "uc1"] as const;
export type KettenUc = (typeof KETTE)[number];

/** Längste Frage, die die Route annimmt. */
export const MAX_FRAGE = 500;

/** Ein UC ohne Antwort; `grund` ist `kein_adapter` oder der Name des Fehlertyps. */
export const fehlendSchema = z
  .object({
    uc: z.enum(KETTE),
    grund: z.string(),
  })
  .strict();

export const ergebnisSchema = z
  .object({
    antworten: z.array(ucAntwortSchema),
    fehlend: z.array(fehlendSchema),
  })
  .strict();

/** Modelle, die man auf /uc4 wählen kann; der Wert geht als LLM_PROVIDER an den Router (plattform.llm). */
export const MODELLWAHL = ["azure", "mistral", "claude", "mock"] as const;
export type Modellwahl = (typeof MODELLWAHL)[number];
/** Beschriftung der Wahl, für Menschen ohne Fachwissen. */
export const MODELL_NAMEN: Record<Modellwahl, string> = {
  azure: "Azure",
  mistral: "Mistral",
  claude: "Claude",
  mock: "Testbetrieb",
};

export const frageSchema = z.object({
  frage: z.string().trim().min(1, "Bitte eine Frage eingeben.").max(MAX_FRAGE, `Höchstens ${MAX_FRAGE} Zeichen.`),
  /** Ohne Angabe gilt LLM_PROVIDER der App. */
  modell: z.enum(MODELLWAHL, { message: "Dieses Modell gibt es hier nicht." }).optional(),
});

export type Fehlend = z.infer<typeof fehlendSchema>;
export type Ergebnis = z.infer<typeof ergebnisSchema>;

/** Hinweis, wenn das Tagesbudget der Modellaufrufe verbraucht ist (Route 429, Karte mitten in der Kette, #100). */
export const BUDGET_MELDUNG = "Für heute sind keine Antworten mehr frei. Bitte morgen wieder fragen.";

/** Lesbarer Grund für eine fehlende Antwort; `BudgetErschoepft` ist der Fehlertyp aus `plattform.llm`. */
export function grundText(grund: string): string {
  if (grund === "kein_adapter") return "Noch nicht angeschlossen";
  if (grund === "BudgetErschoepft") return BUDGET_MELDUNG;
  // plattform.llm lehnt einen Anbieter ab, den der Zweck nicht erlaubt (StatAgent nie mit Claude).
  if (grund === "ZweckFehler") return "Mit diesem Modell gesperrt";
  return "Antwort fehlgeschlagen";
}
