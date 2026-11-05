import { pruefeHerkunft } from "@/components/uc3/anfrage-schutz";
import { auftragWeg, vorfuehrungOffen } from "@/components/uc3/auftrag";

// Nur Vorführ-Instanz (KIC_VORFUEHRUNG=1), die öffentliche Demo antwortet 403 und Caddy lässt das POST dort gar nicht
// durch. POST /api/uc3/auftrag {art:"agent", anweisung} oder {art:"lauf", lieferung}: startet `uc3 agent` bzw. `uc3 lauf`
// im Hintergrund, 202 {stand}; 400 ungültig, 409 es läuft schon einer, 413 zu lang. GET: {stand} des letzten Auftrags.
// Logik und Tests: web/components/uc3/auftrag.ts.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function POST(anfrage: Request): Promise<Response> {
  if (vorfuehrungOffen()) {
    const abgewiesen = pruefeHerkunft(anfrage);
    if (abgewiesen) return Promise.resolve(abgewiesen);
  }
  return auftragWeg.starte(anfrage);
}

export function GET(): Response {
  return auftragWeg.stand();
}
