import { istMockId, mockBericht } from "../../_lib/mock";
import { fehler, gueltigeId, mockErzwungen, ruftApi } from "../../_lib/proxy";

// GET /api/uc2/faelle/{id}: Bericht-JSON des Falls. Kennungen mit "mock-" liefern den aufgezeichneten Fall.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(_anfrage: Request, { params }: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await params;
  if (!gueltigeId(id)) return fehler(400, "Ungültige Fall-Kennung.");
  if (istMockId(id) || mockErzwungen()) {
    const bericht = mockBericht(id);
    return bericht ? Response.json(bericht, { headers: { "cache-control": "no-store" } }) : fehler(404, "Fall nicht gefunden.");
  }
  const antwort = await ruftApi(`/faelle/${encodeURIComponent(id)}`);
  if (!antwort) return fehler(502, "Die Schnittstelle des Panels ist nicht erreichbar.");
  return new Response(antwort.body, {
    status: antwort.status,
    headers: { "content-type": antwort.headers.get("content-type") ?? "application/json", "cache-control": "no-store" },
  });
}
