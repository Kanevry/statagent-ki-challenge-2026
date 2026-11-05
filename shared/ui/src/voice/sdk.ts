// Die Teile des Vapi-Web-SDK (@vapi-ai/web 3.x), die der VoiceKnopf nutzt. @kic/ui hängt bewusst nicht von
// @vapi-ai/web ab: die App reicht einen Lader herein, der das SDK erst beim ersten Klick im Browser importiert.
// So greift beim Server-Rendern nichts auf `window`, und Tests geben ein gefälschtes Objekt hinein.

/** Nachricht aus dem Ereignis `message`; ausgewertet wird nur `type: "transcript"`. */
export type VoiceNachricht = {
  type?: string;
  role?: string;
  transcriptType?: string;
  transcript?: string;
};

export interface VoiceSdk {
  start(assistantId: string): Promise<unknown>;
  stop(): Promise<void> | void;
  on(ereignis: "call-start" | "call-end" | "speech-start" | "speech-end", f: () => void): unknown;
  on(ereignis: "volume-level" | "local-volume-level", f: (pegel: number) => void): unknown;
  on(ereignis: "message", f: (nachricht: VoiceNachricht) => void): unknown;
  on(ereignis: "error", f: (fehler: unknown) => void): unknown;
  removeAllListeners?(): unknown;
}

/** Erzeugt das SDK mit dem öffentlichen Schlüssel, z. B. `async (k) => new (await import("@vapi-ai/web")).default(k)`. */
export type VoiceSdkLader = (publicKey: string) => Promise<VoiceSdk>;

/** Transkript-Abschnitt, den `onTranskript` erhält. Nur finale Abschnitte, nie Zwischenstände. */
export type VoiceTranskript = { rolle: "nutzer" | "assistent"; text: string };

const mikrofonNamen = /NotAllowedError|NotFoundError|PermissionDeniedError|NotReadableError/;
const mikrofonText = /permission|microphone|mikrofon|getUserMedia|audio device|not allowed/i;

/** Liest Name und Meldung eines Fehlers aus, auch verschachtelt (Vapi und Daily packen Fehler in `error`). */
function fehlerTexte(fehler: unknown, tiefe = 0): string[] {
  if (tiefe > 3 || fehler === null || fehler === undefined) return [];
  if (typeof fehler === "string") return [fehler];
  if (typeof fehler !== "object") return [];
  const o = fehler as Record<string, unknown>;
  const eigene = [o.name, o.message, o.type, o.errorMsg].filter((t): t is string => typeof t === "string");
  return [...eigene, ...fehlerTexte(o.error, tiefe + 1), ...fehlerTexte(o.cause, tiefe + 1)];
}

/** true, wenn der Browser das Mikrofon verweigert hat oder keines findet. */
export function istMikrofonFehler(fehler: unknown): boolean {
  return fehlerTexte(fehler).some((t) => mikrofonNamen.test(t) || mikrofonText.test(t));
}
