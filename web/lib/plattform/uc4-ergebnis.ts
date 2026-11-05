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

export const frageSchema = z.object({
  frage: z.string().trim().min(1, "Bitte eine Frage eingeben.").max(MAX_FRAGE, `Höchstens ${MAX_FRAGE} Zeichen.`),
});

export type Fehlend = z.infer<typeof fehlendSchema>;
export type Ergebnis = z.infer<typeof ergebnisSchema>;

/** Lesbarer Grund für eine fehlende Antwort. */
export function grundText(grund: string): string {
  return grund === "kein_adapter" ? "Noch nicht angeschlossen" : "Antwort fehlgeschlagen";
}
