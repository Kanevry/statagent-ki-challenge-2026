import type { VoiceSdkLader } from "@kic/ui/voice";

// Lädt @vapi-ai/web erst beim ersten Klick im Browser (eigener Chunk, kein Zugriff auf `window` beim Rendern).
// Für alle Räume: `<VoiceKnopf ladeSdk={ladeVapi} />` (import aus @/lib/plattform/voice-lader).
export const ladeVapi: VoiceSdkLader = async (publicKey) => {
  const { default: Vapi } = await import("@vapi-ai/web");
  return new Vapi(publicKey);
};
