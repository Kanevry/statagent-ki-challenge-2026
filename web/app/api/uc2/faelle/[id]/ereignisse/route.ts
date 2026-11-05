import { istMockId, mockEreignisse, mockStrom, mockTakt } from "../../../_lib/mock";
import { fehler, gueltigeId, mockErzwungen, ruftApi, SSE_KOPF } from "../../../_lib/proxy";

// GET /api/uc2/faelle/{id}/ereignisse?seq=n: Server-Sent Events. `id: seq`, `event: art`, `data: json`, Wiederaufnahme
// über `Last-Event-ID` oder `?seq=`, Ende mit `event: ende`. Echte Fälle reichen den Strom der Python-API unverändert
// durch; "mock-"-Fälle spielen den Aufgezeichneten zeitversetzt ab (UC2_MOCK_TAKT_MS, Standard 150 ms je Ereignis).
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function startNummer(anfrage: Request): number {
  const url = new URL(anfrage.url);
  const roh = anfrage.headers.get("last-event-id") ?? url.searchParams.get("seq") ?? "0";
  const nummer = Number.parseInt(roh, 10);
  return Number.isFinite(nummer) && nummer > 0 ? nummer : 0;
}

export async function GET(anfrage: Request, { params }: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await params;
  if (!gueltigeId(id)) return fehler(400, "Ungültige Fall-Kennung.");
  const ab = startNummer(anfrage);

  if (istMockId(id) || mockErzwungen()) {
    const ereignisse = mockEreignisse(id);
    if (!ereignisse) return fehler(404, "Fall nicht gefunden.");
    return new Response(mockStrom(ereignisse, ab, mockTakt(), anfrage.signal), { headers: SSE_KOPF });
  }

  const kopf: Record<string, string> = { accept: "text/event-stream" };
  const letzte = anfrage.headers.get("last-event-id");
  if (letzte) kopf["last-event-id"] = letzte;
  const antwort = await ruftApi(`/faelle/${encodeURIComponent(id)}/ereignisse?seq=${ab}`, {
    headers: kopf,
    signal: anfrage.signal,
    frist: 5000,
  });
  if (!antwort) return fehler(502, "Die Schnittstelle des Panels ist nicht erreichbar.");
  if (!antwort.ok || !antwort.body) return fehler(antwort.status === 404 ? 404 : 502, "Der Strom des Falls ist nicht verfügbar.");
  return new Response(antwort.body, { status: 200, headers: SSE_KOPF });
}
