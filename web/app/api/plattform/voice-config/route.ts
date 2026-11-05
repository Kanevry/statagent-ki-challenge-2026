// GET /api/plattform/voice-config (#61): Vapi-Konfiguration für den VoiceKnopf, zur Laufzeit gelesen.
// `next build` hatte NEXT_PUBLIC_VAPI_PUBLIC_KEY leer eingesetzt (Review !4), deshalb kommt der Schlüssel von hier.
// Ausgeliefert wird nur der öffentliche Schlüssel, der für den Browser bestimmt ist. VAPI_API_KEY,
// VAPI_WEBHOOK_SECRET und VAPI_CUSTOM_LLM_KEY werden hier nie gelesen.
// `aktiv` heißt: Voice ist eingerichtet (öffentlicher Schlüssel und PUBLIC_URL für den Custom-LLM-Weg). Den
// Assistenten prüft der Knopf selbst, damit ein Raum mit eigenem Assistenten auch ohne Standard-Assistent geht (#120).
export const dynamic = "force-dynamic";

function wert(name: "VAPI_PUBLIC_KEY" | "VAPI_ASSISTANT_ID" | "PUBLIC_URL" | "KIC_ONLINE_LESEND"): string | null {
  const roh = process.env[name]?.trim();
  return roh ? roh : null;
}

export async function GET(): Promise<Response> {
  const publicKey = wert("VAPI_PUBLIC_KEY");
  const assistantId = wert("VAPI_ASSISTANT_ID");
  // Online-Demo nur lesend (#100): kein Sprechknopf, sonst startete jeder Besucher abgerechnete Vapi-Anrufe,
  // die nach der Begrüßung abbrechen (der Proxy sperrt POST /chat/completions). Review !66.
  const aktiv = Boolean(publicKey && wert("PUBLIC_URL")) && wert("KIC_ONLINE_LESEND") !== "1";
  // Schlüssel und Assistent nur, wenn Voice aktiv ist (Lead a7, 05.11.): Mit dem öffentlichen Schlüssel kann jeder
  // abgerechnete Anrufe starten, auch wenn der Knopf aus ist. Ausgeschaltet heißt deshalb: nichts ausliefern.
  const antwort = aktiv ? { publicKey, assistantId, aktiv } : { publicKey: null, assistantId: null, aktiv };
  return Response.json(antwort, { headers: { "cache-control": "no-store" } });
}
