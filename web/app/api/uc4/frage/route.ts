import { frageAntwort } from "@/lib/plattform/uc4";

// POST /api/uc4/frage mit {frage: string, modell?: "azure"|"mistral"|"claude"|"mock", station?: "uc2"} (Frage 1 bis 500 Zeichen;
// station fragt nur diese Station, /uc2/frage; 403, wenn sie nicht in UC4_KETTE steht;
// modell gilt als LLM_PROVIDER nur für diesen Lauf, online nur mock oder UC4_MODELLWAHL): Ergebnis der Kette
// uc3 → uc2 → uc1 als {antworten, fehlend}. 400 ungültige Frage oder nicht erlaubtes Modell, 403 Online-Demo nur lesend (KIC_ONLINE_LESEND=1), 413 Body über 4 KiB,
// 429 Ratenlimit je IP (RATENLIMIT_PRO_MINUTE), schon zwei Läufe offen oder Tagesbudget der Modellaufrufe erschöpft
// (#100, jeweils mit Hinweis im Feld fehler), 502, wenn der Router nicht oder falsch antwortet.
// Logik und Tests: web/lib/plattform/uc4.ts.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function POST(anfrage: Request): Promise<Response> {
  return frageAntwort(anfrage);
}
