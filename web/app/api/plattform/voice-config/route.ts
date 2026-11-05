// GET /api/plattform/voice-config (#61): Vapi-Konfiguration für den VoiceKnopf, zur Laufzeit gelesen.
// `next build` hatte NEXT_PUBLIC_VAPI_PUBLIC_KEY leer eingesetzt (Review !4), deshalb kommt der Schlüssel von hier.
// Ausgeliefert wird nur der öffentliche Schlüssel, der für den Browser bestimmt ist. VAPI_API_KEY,
// VAPI_WEBHOOK_SECRET und VAPI_CUSTOM_LLM_KEY werden hier nie gelesen.
// `aktiv` heißt: Voice ist eingerichtet (öffentlicher Schlüssel und PUBLIC_URL für den Custom-LLM-Weg). Den
// Assistenten prüft der Knopf selbst, damit ein Raum mit eigenem Assistenten auch ohne Standard-Assistent geht (#120).
export const dynamic = "force-dynamic";

function wert(name: "VAPI_PUBLIC_KEY" | "VAPI_ASSISTANT_ID" | "PUBLIC_URL"): string | null {
  const roh = process.env[name]?.trim();
  return roh ? roh : null;
}

export async function GET(): Promise<Response> {
  const publicKey = wert("VAPI_PUBLIC_KEY");
  const assistantId = wert("VAPI_ASSISTANT_ID");
  const aktiv = Boolean(publicKey && wert("PUBLIC_URL"));
  return Response.json({ publicKey, assistantId, aktiv }, { headers: { "cache-control": "no-store" } });
}
