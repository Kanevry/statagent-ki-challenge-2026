import { z } from "zod";

// Vertrag der Route GET /api/plattform/voice-config (#61). Der Schlüssel kommt zur Laufzeit, nicht zur
// Build-Zeit: `next build` hatte NEXT_PUBLIC_VAPI_PUBLIC_KEY leer eingesetzt (Review !4).
// `publicKey` ist der öffentliche Vapi-Schlüssel, der für den Browser bestimmt ist. Der API-Schlüssel kommt hier nie vor.
export const voiceKonfigurationSchema = z.object({
  publicKey: z.string().min(1).nullable(),
  assistantId: z.string().min(1).nullable(),
  aktiv: z.boolean(),
});

export type VoiceKonfiguration = z.infer<typeof voiceKonfigurationSchema>;

export const VOICE_KONFIGURATION_QUELLE = "/api/plattform/voice-config";
