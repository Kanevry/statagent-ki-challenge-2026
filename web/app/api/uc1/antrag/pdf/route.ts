import { antragPdf } from "@/components/uc1/antrag-server";

// GET /api/uc1/antrag/pdf?art=<art>&sitzung=<uuid>: der vom Kern erzeugte Entwurf als Download. 400 ungültige Art
// oder Sitzung, 403 Online-Demo, 404 Datei fehlt. Pfadprüfung und Tests: web/components/uc1/antrag-server.ts.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function GET(anfrage: Request): Promise<Response> {
  return antragPdf(anfrage);
}
