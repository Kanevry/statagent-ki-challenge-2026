import { protokollAntwort } from "@/lib/plattform/protokoll";

// Fallback für GET /api/<uc>/protokoll, solange ein UC keinen eigenen Handler hat: liefert in Entwicklung
// (NODE_ENV ≠ production) oder mit KIC_FIXTURE=1 die Fixture `shared/schema/fixtures/protokoll-eintraege.json`,
// gefiltert auf den UC, `?status=` wie im Vertrag; in Produktion eine leere Liste (Leerzustand der Schublade).
// Ein UC ersetzt ihn mit web/app/api/<uc>/protokoll/route.ts (statische Route gewinnt), Vorlage:
//   export const GET = (anfrage: Request) => protokollAntwort(anfrage, "uc3", ladeAusDatenbank);
export const dynamic = "force-dynamic";

export async function GET(anfrage: Request, { params }: { params: Promise<{ uc: string }> }): Promise<Response> {
  const { uc } = await params;
  return protokollAntwort(anfrage, uc);
}
