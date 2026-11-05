import { z } from "zod";

// Antwort von GET /api/plattform/modell, gleich der Ausgabe von `python -m plattform.llm status --json`.
// Ohne "use client", damit der Route-Handler dasselbe Schema nutzt wie der Badge.
export const modellStatusSchema = z.object({
  provider: z.string(),
  modell: z.string(),
  version: z.string().nullable(),
  quelle: z.string(),
});
export type ModellStatus = z.infer<typeof modellStatusSchema>;

/** Antwort, wenn der Modell-Schalter nicht antwortet (Route liefert dazu 503). */
export const modellUnbekannt: ModellStatus = { provider: "unbekannt", modell: "unbekannt", version: null, quelle: "fehler" };
