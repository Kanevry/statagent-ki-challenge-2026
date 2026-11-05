import { pruefeHerkunft } from "@/components/uc3/anfrage-schutz";
import { erstelleFrageAntwort } from "@/components/uc3/antwort";
import { nurLesend, uc3 } from "@/components/uc3/cli";

// POST /api/uc3/frage mit {frage: string} (1 bis 500 Zeichen): Antwort aus der UC3-Datenbank ohne Sprachmodell als
// {antwort: UcAntwort, definition, rueckfrage, quelle}. 400 ungültige Frage, 403 Online-Demo (KIC_ONLINE_LESEND=1)
// oder fremde Seite, 413 Body über 4 KiB, 415 kein JSON, 429 schon zwei Läufe offen, 502 bei Zeitüberschreitung
// oder falscher Ausgabe. Logik und Tests: web/components/uc3/antwort.ts, web/components/uc3/anfrage-schutz.ts.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Prozessweiter Handler; höchstens zwei CLI-Läufe gleichzeitig. */
const frageAntwort = erstelleFrageAntwort({ starte: uc3 });

export function POST(anfrage: Request): Promise<Response> {
  // Die Online-Demo antwortet immer mit ihrem eigenen Satz (403); sonst zuerst die Herkunft prüfen (CSRF).
  if (!nurLesend()) {
    const abgewiesen = pruefeHerkunft(anfrage);
    if (abgewiesen) return Promise.resolve(abgewiesen);
  }
  return frageAntwort(anfrage);
}
