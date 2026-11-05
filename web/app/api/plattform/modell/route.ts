import { leseModell } from "@/lib/plattform/modell";

// GET /api/plattform/modell: aktiver Provider und Modell für den Modell-Badge (Vertrag H).
// 200 mit {provider, modell, version, quelle}; 503 mit provider "unbekannt", wenn der Schalter nicht antwortet.
export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  const { status, body } = await leseModell();
  return Response.json(body, { status, headers: { "cache-control": "no-store" } });
}
