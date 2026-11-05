import { frageAntwort } from "@/lib/plattform/uc4";

// POST /api/uc4/frage mit {frage: string} (1 bis 500 Zeichen): Ergebnis der Kette uc3 → uc2 → uc1 als
// {antworten, fehlend}. 400 bei ungültiger Frage, 429 bei Ratenlimit je IP oder erschöpftem Tagesbudget (#100),
// 502, wenn der Router nicht oder falsch antwortet.
// Logik und Tests: web/lib/plattform/uc4.ts.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function POST(anfrage: Request): Promise<Response> {
  return frageAntwort(anfrage);
}
