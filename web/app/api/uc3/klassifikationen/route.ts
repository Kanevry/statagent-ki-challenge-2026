import { anfrageAus, leseAnfrage } from "@/components/uc3/klassifikation-tief";

// GET /api/uc3/klassifikationen?art=oenace|region&fassung=2025|2026-01-01[&unter=CODE|&suche=TEXT] für das Nachschlagen auf
// /uc3/klassifikationen: oberste Ebene, Kinder eines Codes oder Treffer der Suche. Nur lesend. 400 bei ungültigen Parametern,
// 503 ohne Datenbank. Logik und Tests: web/components/uc3/klassifikation-tief.ts.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const KOPF = { "cache-control": "no-store" };

export async function GET(anfrage: Request): Promise<Response> {
  const geprueft = anfrageAus(new URL(anfrage.url).searchParams);
  if (!geprueft) return Response.json({ fehler: "Diese Anfrage verstehe ich nicht." }, { status: 400, headers: KOPF });
  const lesung = await leseAnfrage(geprueft);
  if (!lesung.ok) return Response.json({ fehler: "Die Liste ist gerade nicht erreichbar." }, { status: 503, headers: KOPF });
  return Response.json(lesung.daten, { headers: KOPF });
}
