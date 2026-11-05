import { GET as ereignisse } from "./faelle/[id]/ereignisse/route";
import { GET as bericht } from "./faelle/[id]/route";
import { GET as liste, POST as starten } from "./faelle/route";

// Der Mock-Handler liefert SSE wie die echte Schnittstelle (id, event, data, Ende mit "event: ende"); ohne erreichbare
// API und mit UC2_MOCK=1 antworten die Handler mit dem aufgezeichneten Fall; echte Fälle gehen durch.

const ctx = (id: string) => ({ params: Promise.resolve({ id }) });
const post = (body: unknown, roh?: string) =>
  starten(new Request("http://x/api/uc2/faelle", { method: "POST", headers: { "content-type": "application/json" }, body: roh ?? JSON.stringify(body) }));

beforeEach(() => {
  vi.stubEnv("UC2_MOCK_TAKT_MS", "0");
  vi.stubEnv("UC2_MOCK", "1");
  vi.stubEnv("OLLAMA_MODEL", "");
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

function bloecke(text: string): { id?: string; event?: string; data?: string }[] {
  return text
    .split("\n\n")
    .filter((b) => b.trim() !== "" && !b.startsWith("retry:"))
    .map((b) => Object.fromEntries(b.split("\n").map((z) => [z.slice(0, z.indexOf(":")), z.slice(z.indexOf(":") + 2)])));
}

it("liefert den aufgezeichneten Fall als SSE und endet mit event: ende", async () => {
  const antwort = await ereignisse(new Request("http://x/api/uc2/faelle/mock-wartezeiten/ereignisse"), ctx("mock-wartezeiten"));
  expect(antwort.status).toBe(200);
  expect(antwort.headers.get("content-type")).toContain("text/event-stream");
  const text = await antwort.text();
  expect(text).toContain("event: ende");
  const teile = bloecke(text);
  expect(teile).toHaveLength(67);
  expect(teile.at(-1)).toEqual({ event: "ende", data: JSON.stringify({ status: "fertig", letzte_seq: 66 }) });
  expect(teile.slice(0, 66).map((b) => Number(b.id))).toEqual(Array.from({ length: 66 }, (_, i) => i + 1));
  expect(JSON.parse(teile[0]!.data!)).toMatchObject({ seq: 1, art: "start" });
});

it("setzt über Last-Event-ID und ?seq= ab der genannten Nummer fort", async () => {
  const mitKopf = await ereignisse(
    new Request("http://x/api/uc2/faelle/mock-wartezeiten/ereignisse", { headers: { "last-event-id": "60" } }),
    ctx("mock-wartezeiten"),
  );
  expect(bloecke(await mitKopf.text()).map((b) => b.id)).toEqual(["61", "62", "63", "64", "65", "66", undefined]);
  const mitSeq = await ereignisse(new Request("http://x/api/uc2/faelle/mock-wartezeiten/ereignisse?seq=65"), ctx("mock-wartezeiten"));
  expect(bloecke(await mitSeq.text()).map((b) => b.id)).toEqual(["66", undefined]);
});

it("der Abbruch-Fall endet mit dem Ereignis abbruch nach Runde 2 und event: ende abgebrochen mit letzte_seq", async () => {
  const antwort = await ereignisse(new Request("http://x/api/uc2/faelle/mock-abbruch/ereignisse"), ctx("mock-abbruch"));
  const teile = bloecke(await antwort.text());
  const arten = teile.map((b) => b.event);
  expect(arten.at(-2)).toBe("abbruch");
  expect(arten).not.toContain("fehler");
  expect(arten.at(-1)).toBe("ende");
  expect(JSON.parse(teile.at(-1)!.data!)).toEqual({ status: "abgebrochen", letzte_seq: 37 });
  const abbruch = JSON.parse(teile.at(-2)!.data!) as { seq: number; runde: number; daten: { grund: string; meldung: string } };
  expect(abbruch).toMatchObject({ seq: 37, runde: 3, daten: { grund: "TimeoutError" } });
  expect(abbruch.daten.meldung.length).toBeLessThanOrEqual(300);
  expect(JSON.parse(teile[0]!.data!).daten).toMatchObject({ provider: "azure" });
  expect(arten.filter((a) => a === "runde_ende")).toHaveLength(2);
});

it("lehnt ungültige Kennungen ab und kennt unbekannte Mock-Fälle nicht", async () => {
  expect((await ereignisse(new Request("http://x/"), ctx("a/../b"))).status).toBe(400);
  expect((await ereignisse(new Request("http://x/"), ctx("mock-gibt-es-nicht"))).status).toBe(404);
  expect((await bericht(new Request("http://x/"), ctx("mock-gibt-es-nicht"))).status).toBe(404);
});

it("Bericht und Liste kommen im Mock-Modus aus dem aufgezeichneten Fall", async () => {
  const b = (await (await bericht(new Request("http://x/"), ctx("mock-abbruch"))).json()) as { fall: { fall_id: string; status: string }; runden: unknown[] };
  expect(b.fall).toMatchObject({ fall_id: "mock-abbruch", status: "abgebrochen" });
  expect(b.runden).toHaveLength(2);
  const l = (await (await liste()).json()) as { fall_id: string }[];
  expect(l.map((f) => f.fall_id)).toEqual(["mock-wartezeiten", "mock-abbruch"]);
});

it("POST /faelle startet im Mock-Modus mit 202, prüft den Body und kennt ollama nur, wenn es eingerichtet ist", async () => {
  const ok = await post({ provider: "azure" });
  expect(ok.status).toBe(202);
  expect(await ok.json()).toEqual({ fall_id: "mock-wartezeiten", status: "laeuft", quelle: "mock" });
  expect((await post(null, "kein json")).status).toBe(400);
  expect((await post({ provider: "gpt" })).status).toBe(400);
  expect((await post({ akteure: ["a", "b", "c", "d", "e", "f", "g"] })).status).toBe(400);
  expect((await post({ frage: "x".repeat(600) })).status).toBe(400);
  expect((await post({ provider: "ollama" })).status).toBe(422);
  vi.stubEnv("OLLAMA_MODEL", "qwen3:8b");
  expect((await post({ provider: "ollama" })).status).toBe(202);
});

describe("ohne UC2_MOCK", () => {
  beforeEach(() => vi.stubEnv("UC2_MOCK", ""));

  it("fällt auf den aufgezeichneten Fall zurück, wenn die API nicht erreichbar ist", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("fetch failed"))));
    const antwort = await post({});
    expect(antwort.status).toBe(202);
    expect(((await antwort.json()) as { quelle: string }).quelle).toBe("mock");
    expect((await liste()).status).toBe(200);
  });

  it("reicht Start, Fehlerstatus und SSE-Strom der API unverändert durch", async () => {
    const abruf = vi.fn(async (adresse: string | URL | Request, optionen?: RequestInit) => {
      const url = String(adresse);
      if (url.endsWith("/faelle") && optionen?.method === "POST") return Response.json({ fall_id: "17", status: "laeuft" }, { status: 202 });
      if (url.includes("/faelle/17/ereignisse")) {
        return new Response("id: 5\nevent: zug\ndata: {}\n\nevent: ende\ndata: {}\n\n", { headers: { "content-type": "text/event-stream" } });
      }
      return new Response("{}", { status: 404 });
    });
    vi.stubGlobal("fetch", abruf);
    const start = await post({ provider: "claude" });
    expect(start.status).toBe(202);
    expect(await start.json()).toEqual({ fall_id: "17", status: "laeuft" });
    expect(String(abruf.mock.calls[0]?.[0])).toBe("http://localhost:8102/faelle");

    const strom = await ereignisse(new Request("http://x/", { headers: { "last-event-id": "4" } }), ctx("17"));
    expect(strom.headers.get("content-type")).toContain("text/event-stream");
    expect(await strom.text()).toContain("event: ende");
    expect(String(abruf.mock.calls.at(-1)?.[0])).toContain("/faelle/17/ereignisse?seq=4");
  });

  it("gibt 409 der API weiter und meldet 502, wenn der Strom eines echten Falls nicht zu erreichen ist", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ detail: "läuft schon" }, { status: 409 })));
    expect((await post({})).status).toBe(409);
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("fetch failed"))));
    expect((await ereignisse(new Request("http://x/"), ctx("17"))).status).toBe(502);
  });

  it("wiederholt den Start ohne akteure, wenn die API sie mit 422 ablehnt, und sagt es im Kopf", async () => {
    const abruf = vi.fn(async (_u: string | URL | Request, o?: RequestInit) =>
      String(o?.body).includes("akteure") ? new Response("{}", { status: 422 }) : Response.json({ fall_id: "9", status: "laeuft" }, { status: 202 }),
    );
    vi.stubGlobal("fetch", abruf);
    const antwort = await post({ akteure: ["sv", "patienten"] });
    expect(antwort.status).toBe(202);
    expect(antwort.headers.get("x-uc2-akteure")).toBe("ignoriert");
    expect(abruf).toHaveBeenCalledTimes(2);
  });
});
