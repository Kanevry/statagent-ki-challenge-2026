import { protokollAntwort } from "@/lib/plattform/protokoll";
import { protokollQuelle } from "@/lib/uc3/protokoll";

// GET /api/uc3/protokoll[?status=offen|freigegeben|abgelehnt] (Vertrag H/P): Einträge aus meta.protokoll der
// UC3-Datenbank, neueste zuerst, geprüft gegen das Schema `Eintrag`. Ohne Datenbank eine leere Liste, nie Fixtures.
export const dynamic = "force-dynamic";

export function GET(anfrage: Request): Promise<Response> {
  return protokollAntwort(anfrage, "uc3", protokollQuelle);
}
