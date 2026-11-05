import { z } from "zod";
import { erstelleRatenlimit, grenzeAus } from "../../../../lib/plattform/ratenlimit";
import { leseBodyText, ZuGross } from "../_lib/body";
import { MOCK_FALL, mockListe } from "../_lib/mock";
import { fehler, fehlerAusApiStatus, MODUS_KOPF, mockErzwungen, ruftApi } from "../_lib/proxy";
import { ollamaKonfiguriert } from "../_lib/vorbereitung";

// POST /api/uc2/faelle  {fall?, frage?, provider?, belege?, akteure?}: startet einen Fall, 202 {fall_id, status}.
// GET  /api/uc2/faelle: Liste mit Status.
// Beides reicht an `uc2.api` (UC2_API_URL, Standard http://localhost:8102) durch. Ist die API nicht erreichbar oder
// UC2_MOCK=1 gesetzt, antwortet der aufgezeichnete Fall (Kennung mock-wartezeiten). `web/` ruft nie ein Modell.
// `akteure` ist eine Erweiterung des Vertrags (Auswahl auf U2-0); lehnt die API sie ab (422), geht der Start ohne
// sie noch einmal durch und die Antwort trägt den Kopf `x-uc2-akteure: ignoriert`.
//
// Sperren von POST, alle vor dem Body und vor jedem API-Aufruf (Muster: /api/uc4/frage): KIC_ONLINE_LESEND=1 → 403
// (zweite Sperre hinter dem Proxy, deploy/README.md), Ratenlimit je Client-IP → 429, Body über 4 KiB (auch gestreamt
// ohne Content-Length) → 413. Fehlerkörper der API gehen nie nach außen, nur feste Sätze.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const MAX_BODY = 4 * 1024;

const startSchema = z.object({
  fall: z.string().regex(/^[a-z0-9-]{1,40}$/).default("wartezeiten"),
  frage: z.string().trim().min(1).max(500).optional(),
  provider: z.enum(["mock", "claude", "azure", "ollama"]).optional(),
  belege: z.enum(["fixture", "index"]).optional(),
  akteure: z.array(z.string().regex(/^[a-z0-9_]{1,40}$/)).max(6).optional(),
});

const antwortSchema = z.object({ fall_id: z.union([z.string(), z.number()]), status: z.string().optional() });

const KEIN_CACHE = { "cache-control": "no-store" } as const;

const ratenlimit = erstelleRatenlimit({ proMinute: grenzeAus(process.env) });

export async function POST(anfrage: Request): Promise<Response> {
  if (process.env.KIC_ONLINE_LESEND === "1") return fehler(403, "Starten ist in der Online-Demo gesperrt.");
  const gedrosselt = ratenlimit(anfrage);
  if (gedrosselt) return gedrosselt;

  let roh: unknown;
  try {
    const text = await leseBodyText(anfrage, MAX_BODY);
    roh = text.trim() === "" ? {} : JSON.parse(text);
  } catch (f) {
    return f instanceof ZuGross ? fehler(413, "Die Anfrage ist zu groß.") : fehler(400, "Die Anfrage braucht JSON.");
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
      if (!antwort.ok) return fehlerAusApiStatus(antwort.status);
      const geprueft = antwortSchema.safeParse(await antwort.json().catch(() => null));
      if (!geprueft.success) return fehler(502, "Das Panel hat in einem unerwarteten Format geantwortet.");
      const kopf: Record<string, string> = { ...KEIN_CACHE, [MODUS_KOPF]: "live" };
      if (ignoriert) kopf["x-uc2-akteure"] = "ignoriert";
      return Response.json(
        { fall_id: String(geprueft.data.fall_id), status: geprueft.data.status ?? "laeuft" },
        { status: antwort.status === 200 ? 200 : 202, headers: kopf },
      );
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
      if (!antwort.ok) return fehlerAusApiStatus(antwort.status);
      return new Response(antwort.body, {
        status: 200,
        headers: { "content-type": antwort.headers.get("content-type") ?? "application/json", ...KEIN_CACHE },
      });
    }
  }
  return Response.json(mockListe(), { headers: KEIN_CACHE });
}
