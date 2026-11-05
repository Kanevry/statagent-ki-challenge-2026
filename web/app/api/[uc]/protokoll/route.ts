import { protokollAntwort } from "@/lib/plattform/protokoll";

// Fallback für GET /api/<uc>/protokoll, solange ein UC keinen eigenen Handler hat: liefert die Fixture
// `shared/schema/fixtures/protokoll-eintraege.json`, gefiltert auf den UC, `?status=` wie im Vertrag.
// Ein UC ersetzt ihn mit web/app/api/<uc>/protokoll/route.ts (statische Route gewinnt), Vorlage:
//   export const GET = (anfrage: Request) => protokollAntwort(anfrage, "uc3", ladeAusDatenbank);
export const dynamic = "force-dynamic";

export async function GET(anfrage: Request, { params }: { params: Promise<{ uc: string }> }): Promise<Response> {
  const { uc } = await params;
  return protokollAntwort(anfrage, uc);
}
