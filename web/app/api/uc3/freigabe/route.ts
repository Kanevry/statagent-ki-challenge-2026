import { freigabeAntwort } from "@/lib/uc3/freigabe";

// POST /api/uc3/freigabe mit {id, name, entscheidung: "ja"|"nein", begruendung?}: reicht die Entscheidung eines
// Menschen an `uc3 freigabe` bzw. `uc3 ablehnen` weiter (argv, keine Shell). 200 {zeitpunkt, commit, protokoll_id},
// 400 ungültig oder Name ohne Vor- und Nachname, 403 Online-Demo (KIC_ONLINE_LESEND=1), 409 von der CLI abgewiesen,
// 413 Body über 4 KiB, 429 schon eine Entscheidung offen, 502 CLI nicht erreichbar. Logik und Tests:
// web/lib/uc3/freigabe.ts.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function POST(anfrage: Request): Promise<Response> {
  return freigabeAntwort(anfrage);
}
