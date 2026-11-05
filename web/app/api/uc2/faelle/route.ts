import { z } from "zod";
import { MOCK_FALL, mockListe } from "../_lib/mock";
import { fehler, MODUS_KOPF, mockErzwungen, ruftApi } from "../_lib/proxy";
import { ollamaKonfiguriert } from "../_lib/vorbereitung";

// POST /api/uc2/faelle  {fall?, frage?, provider?, belege?, akteure?}: startet einen Fall, 202 {fall_id, status}.
// GET  /api/uc2/faelle: Liste mit Status.
// Beides reicht an `uc2.api` (UC2_API_URL, Standard http://localhost:8102) durch. Ist die API nicht erreichbar oder
// UC2_MOCK=1 gesetzt, antwortet der aufgezeichnete Fall (Kennung mock-wartezeiten). `web/` ruft nie ein Modell.
// `akteure` ist eine Erweiterung des Vertrags (Auswahl auf U2-0); lehnt die API sie ab (422), geht der Start ohne
// sie noch einmal durch und die Antwort trägt den Kopf `x-uc2-akteure: ignoriert`.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const MAX_BODY = 4 * 1024;

const startSchema = z.object({
  fall: z.string().regex(/^[a-z0-9-]{1,40}$/).default("wartezeiten"),
  frage: z.string().trim().min(1).max(500).optional(),
  provider: z.enum(["mock", "claude", "azure", "ollama"]).optional(),
  belege: z.enum(["fixture", "index"]).optional(),
  akteure: z.array(z.string().regex(/^[a-z0-9_]{1,40}$/)).max(6).optional(),
});

const KEIN_CACHE = { "cache-control": "no-store" } as const;

async function leseBody(anfrage: Request): Promise<unknown> {
  const laenge = Number(anfrage.headers.get("content-length") ?? "0");
  if (laenge > MAX_BODY) throw new RangeError("zu gross");
  const text = await anfrage.text();
  if (new TextEncoder().encode(text).length > MAX_BODY) throw new RangeError("zu gross");
  return text.trim() === "" ? {} : JSON.parse(text);
}

export async function POST(anfrage: Request): Promise<Response> {
  let roh: unknown;
  try {
    roh = await leseBody(anfrage);
  } catch (f) {
    return f instanceof RangeError ? fehler(413, "Die Anfrage ist zu groß.") : fehler(400, "Die Anfrage braucht JSON.");
  }
  const start = startSchema.safeParse(roh);
  if (!start.success) return fehler(400, "Die Anfrage passt nicht: fall, frage, provider, belege oder akteure sind ungültig.");
  const { akteure, ...vertrag } = start.data;

  if (vertrag.provider === "ollama" && !ollamaKonfiguriert()) {
    return fehler(422, "Das lokale Modell ollama ist hier nicht eingerichtet.");
  }

  if (!mockErzwungen()) {
    const senden = (inhalt: object) =>
      ruftApi("/faelle", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(inhalt),
        frist: 5000,
      });
    let antwort = await senden(akteure ? { ...vertrag, akteure } : vertrag);
    let ignoriert = false;
    if (antwort?.status === 422 && akteure) {
      antwort = await senden(vertrag);
      ignoriert = true;
    }
    if (antwort) {
      const kopf = new Headers({ "content-type": antwort.headers.get("content-type") ?? "application/json", [MODUS_KOPF]: "live", ...KEIN_CACHE });
      if (ignoriert) kopf.set("x-uc2-akteure", "ignoriert");
      return new Response(antwort.body, { status: antwort.status, headers: kopf });
    }
  }

  return Response.json(
    { fall_id: MOCK_FALL, status: "laeuft", modus: "vorfuehrung" },
    { status: 202, headers: { ...KEIN_CACHE, [MODUS_KOPF]: "vorfuehrung" } },
  );
}

export async function GET(): Promise<Response> {
  if (!mockErzwungen()) {
    const antwort = await ruftApi("/faelle");
    if (antwort) {
      return new Response(antwort.body, {
        status: antwort.status,
        headers: { "content-type": antwort.headers.get("content-type") ?? "application/json", ...KEIN_CACHE },
      });
    }
  }
  return Response.json(mockListe(), { headers: KEIN_CACHE });
}
