import { excelAntwort } from "@/components/uc3/ergebnisse";

// GET /api/uc3/ergebnisse/v1|v2: nur die Einträge der festen Liste, kein Pfad aus der Eingabe (SEC-006).
export const dynamic = "force-dynamic";

export async function GET(_anfrage: Request, { params }: { params: Promise<{ fassung: string }> }): Promise<Response> {
  return excelAntwort((await params).fassung);
}
