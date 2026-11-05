import { z } from "zod";

// Antwort von GET /api/plattform/modell, gleich der Ausgabe von `python -m plattform.llm status --json`.
// Ohne "use client", damit der Route-Handler dasselbe Schema nutzt wie der Badge.

/** Wer laut Protokoll zuletzt tatsächlich geantwortet hat; `null`, solange noch kein Aufruf lief. */
export const zuletztSchema = z.object({
  provider: z.string(),
  modell: z.string(),
  version: z.string().nullable(),
  /** 1 = gewählter Provider, ab 2 eine Ausweichstufe. */
  fallback_stufe: z.number().int(),
  zweck: z.string().optional(),
  zeit: z.string(),
});
export type Zuletzt = z.infer<typeof zuletztSchema>;

export const modellStatusSchema = z.object({
  provider: z.string(),
  modell: z.string(),
  version: z.string().nullable(),
  quelle: z.string(),
  zuletzt: zuletztSchema.nullable().optional(),
});
export type ModellStatus = z.infer<typeof modellStatusSchema>;

/** Antwort, wenn der Modell-Schalter nicht antwortet (Route liefert dazu 503). */
export const modellUnbekannt: ModellStatus = { provider: "unbekannt", modell: "unbekannt", version: null, quelle: "fehler" };

/**
 * Hat zuletzt jemand anderes geantwortet als gewählt (anderer Provider oder Ausweichstufe > 1)? Dann gehört
 * das in den Badge, damit keine falsche Modellangabe stehen bleibt.
 */
export function abweichendZuletzt(status: ModellStatus): Zuletzt | null {
  const zuletzt = status.zuletzt;
  if (!zuletzt) return null;
  return zuletzt.provider !== status.provider || zuletzt.fallback_stufe > 1 ? zuletzt : null;
}
