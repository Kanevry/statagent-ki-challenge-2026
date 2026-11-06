import { fassungAus } from "@/lib/plattform/fassung";

// GET /api/plattform/fassung: die andere Fassung der Demo für den Knopf im Kopf, zur Laufzeit gelesen, weil der Build die
// Umgebung nicht kennt. Liefert {fassung: null}, wenn keine Adresse gesetzt ist; dann erscheint kein Knopf.
export const dynamic = "force-dynamic";

export function GET(): Response {
  return Response.json({ fassung: fassungAus(process.env) }, { headers: { "cache-control": "no-store" } });
}
