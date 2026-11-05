import { lotseAntwort } from "@/components/uc1/lotse";

// POST /api/uc1/frage mit {text, sitzung?, stil?, sprache?}: Antwort des Lotsen in der Web-Form
// (components/uc1/antwort.ts). 400 ungültige Eingabe, 403 Online-Demo (KIC_ONLINE_LESEND=1, mit replay: true),
// 413 Body über 4 KiB, 429 schon zwei Läufe offen, 503 Lotse nicht erreichbar (mit replay: true).
// Logik und Tests: web/components/uc1/lotse.ts.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function POST(anfrage: Request): Promise<Response> {
  return lotseAntwort(anfrage);
}
