import { protokollAntwort } from "@/lib/plattform/protokoll";

// GET /api/uc1/protokoll: eigener Handler statt des Fallbacks, ohne eigene Datenbank-Quelle (#35).
export const dynamic = "force-dynamic";
export const GET = (anfrage: Request) => protokollAntwort(anfrage, "uc1");
