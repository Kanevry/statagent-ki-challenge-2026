import { leseModell } from "../../../../lib/plattform/modell";
import { apiErreichbar } from "../_lib/vorbereitung";

// GET /api/uc2/modell: Modell-Zustand des UC2-Bereichs im Format von GET /api/plattform/modell (ModellStatus).
// Vorführmodus (UC2_MOCK=1 oder keine Python-API erreichbar): es läuft eine Aufzeichnung ohne Sprachmodell, der Badge
// sagt das ehrlich. Live: der Zustand des Modell-Schalters der Plattform. Der Header-Badge liest diese Route, sobald die
// Shell sie für /uc2 als `modellQuelle` bekommt (siehe Auftrag an E0 im Bericht zu #47).
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(): Promise<Response> {
  const kopf = { "cache-control": "no-store" };
  if (!(await apiErreichbar())) {
    return Response.json(
      { provider: "Testbetrieb", modell: "keine KI angeschlossen", version: null, quelle: "uc2-vorfuehrung" },
      { headers: { ...kopf, "x-uc2-modus": "vorfuehrung" } },
    );
  }
  const { status, body } = await leseModell();
  return Response.json(body, { status, headers: { ...kopf, "x-uc2-modus": "live" } });
}
