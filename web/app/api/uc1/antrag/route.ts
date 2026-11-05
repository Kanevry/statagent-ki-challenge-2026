import { antragAntwort } from "@/components/uc1/antrag-server";

// POST /api/uc1/antrag mit {art, sitzung}: der vom Kern vorausgefüllte Antrag in der Web-Form
// (components/uc1/antrag.ts), ohne PDF-Pfad. 400 ungültige Eingabe, 403 Online-Demo (mit replay: true),
// 413 Body über 1 KiB, 429 schon zwei Läufe offen, 503 Lotse nicht erreichbar (mit replay: true).
// Logik und Tests: web/components/uc1/antrag-server.ts. Abgeschickt wird nichts.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function POST(anfrage: Request): Promise<Response> {
  return antragAntwort(anfrage);
}
