import { GET as ereignisse } from "./faelle/[id]/ereignisse/route";
import { GET as bericht } from "./faelle/[id]/route";
import { GET as liste, POST as starten } from "./faelle/route";
import { GET as modell } from "./modell/route";

// Der Mock-Handler liefert SSE wie die echte Schnittstelle (id, event, data, Ende mit "event: ende"); ohne erreichbare
// API und mit UC2_MOCK=1 antworten die Handler mit dem aufgezeichneten Fall; echte Fälle gehen durch.

const ctx = (id: string) => ({ params: Promise.resolve({ id }) });
let nummer = 0;
// Jede Anfrage kommt von einer eigenen IP, damit das Ratenlimit (10 je Minute und IP) die Tests nicht stört.
const post = (body: unknown, roh?: string, ip = `10.0.0.${++nummer}`) =>
  starten(
    new Request("http://x/api/uc2/faelle", {
      method: "POST",
      headers: { "content-type": "application/json", "x-forwarded-for": ip },
      body: roh ?? JSON.stringify(body),
    }),
  );

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

it("?sofort=1 liefert den Rest ohne Takt: „Zum Ergebnis“ wartet nicht auf die Aufzeichnung", async () => {
  // Fängt einen Takt, der auch hier gilt: Mit 2 s je Ereignis liefe dieser Test in den Zeitablauf.
  vi.stubEnv("UC2_MOCK_TAKT_MS", "2000");
  const antwort = await ereignisse(new Request("http://x/api/uc2/faelle/mock-wartezeiten/ereignisse?seq=10&sofort=1"), ctx("mock-wartezeiten"));
  const teile = bloecke(await antwort.text());
  expect(teile).toHaveLength(57);
  expect(teile[0]!.id).toBe("11");
  vi.unstubAllEnvs();
});

it("liefert den aufgezeichneten Fall als SSE und endet mit event: ende", async () => {
  const antwort = await ereignisse(new Request("http://x/api/uc2/faelle/mock-wartezeiten/ereignisse"), ctx("mock-wartezeiten"));
  expect(antwort.status).toBe(200);
  expect(antwort.headers.get("content-type")).toContain("text/event-stream");
  expect(antwort.headers.get("x-uc2-modus")).toBe("vorfuehrung");
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
  const text = await antwort.text();
  const teile = bloecke(text);
  const arten = teile.map((b) => b.event);
  expect(arten.at(-2)).toBe("abbruch");
  expect(arten).not.toContain("fehler");
  expect(arten.at(-1)).toBe("ende");
  expect(JSON.parse(teile.at(-1)!.data!)).toEqual({ status: "abgebrochen", letzte_seq: 37 });
  const abbruch = JSON.parse(teile.at(-2)!.data!) as { seq: number; runde: number; daten: { grund: string; meldung: string } };
  expect(abbruch).toMatchObject({ seq: 37, runde: 3, daten: { grund: "SimulierterAbbruch" } });
  expect(abbruch.daten.meldung.length).toBeLessThanOrEqual(300);
  // Kein erfundener Anbieter-Ausfall: die Aufzeichnung läuft über das Testmodell.
  expect(JSON.parse(teile[0]!.data!).daten.modelle).toMatchObject({ akteur: { provider: "mock" }, moderator: { provider: "mock" } });
  expect(text).not.toContain("azure");
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
  expect(await ok.json()).toEqual({ fall_id: "mock-wartezeiten", status: "laeuft", modus: "vorfuehrung" });
  expect(ok.headers.get("x-uc2-modus")).toBe("vorfuehrung");
  expect((await post(null, "kein json")).status).toBe(400);
  expect((await post({ provider: "gpt" })).status).toBe(400);
  expect((await post({ akteure: ["a", "b", "c", "d", "e", "f", "g"] })).status).toBe(400);
  expect((await post({ frage: "x".repeat(600) })).status).toBe(400);
  expect((await post({ provider: "ollama" })).status).toBe(422);
  vi.stubEnv("OLLAMA_MODEL", "qwen3:8b");
  expect((await post({ provider: "ollama" })).status).toBe(202);
});

it("GET /api/uc2/modell meldet im Vorführmodus Testbetrieb ohne KI, im Format des Modell-Status", async () => {
  const antwort = await modell();
  expect(antwort.status).toBe(200);
  expect(antwort.headers.get("x-uc2-modus")).toBe("vorfuehrung");
  expect(await antwort.json()).toEqual({ provider: "mock", modell: "mock", version: null, quelle: "uc2-vorfuehrung" });
});

describe("Sperren von POST /faelle", () => {
  it("antwortet mit KIC_ONLINE_LESEND=1 sofort mit 403, ohne den Body zu lesen oder die API zu rufen", async () => {
    vi.stubEnv("KIC_ONLINE_LESEND", "1");
    const abruf = vi.fn();
    vi.stubGlobal("fetch", abruf);
    const anfrage = new Request("http://x/api/uc2/faelle", { method: "POST", body: "{}", headers: { "x-forwarded-for": "10.9.9.9" } });
    const antwort = await starten(anfrage);
    expect(antwort.status).toBe(403);
    expect(await antwort.json()).toEqual({ fehler: "Starten ist in der Online-Demo gesperrt." });
    expect(anfrage.bodyUsed).toBe(false);
    expect(abruf).not.toHaveBeenCalled();
  });

  it("GET bleibt in der Online-Demo erlaubt (Replay)", async () => {
    vi.stubEnv("KIC_ONLINE_LESEND", "1");
    expect((await liste()).status).toBe(200);
    expect((await ereignisse(new Request("http://x/"), ctx("mock-wartezeiten"))).status).toBe(200);
  });

  it("drosselt je IP mit 429 und Retry-After, andere IPs bleiben frei", async () => {
    const ip = "10.7.7.7";
    const stati: number[] = [];
    for (let i = 0; i < 11; i++) stati.push((await post({}, undefined, ip)).status);
    expect(stati.slice(0, 10)).toEqual(Array(10).fill(202));
    expect(stati[10]).toBe(429);
    const gedrosselt = await post({}, undefined, ip);
    expect(gedrosselt.headers.get("retry-after")).toMatch(/^\d+$/);
    expect((await post({}, undefined, "10.7.7.8")).status).toBe(202);
  });

  it("bricht einen zu großen Body auch ohne Content-Length beim Lesen ab (413)", async () => {
    let geliefert = 0;
    const stueck = new TextEncoder().encode("x".repeat(1024));
    const body = new ReadableStream<Uint8Array>({
      pull(c) {
        if (geliefert >= 100) return c.close();
        geliefert += 1;
        c.enqueue(stueck);
      },
    });
    const anfrage = new Request("http://x/api/uc2/faelle", { method: "POST", body, duplex: "half", headers: { "x-forwarded-for": "10.8.8.8" } } as RequestInit);
    expect(anfrage.headers.get("content-length")).toBeNull();
    const antwort = await starten(anfrage);
    expect(antwort.status).toBe(413);
    // Gelesen wurde nur bis knapp über die Grenze (4 KiB), nicht die ganzen 100 KiB.
    expect(geliefert).toBeLessThan(20);
  });

  it("ein zu großer Body mit Content-Length wird ebenfalls mit 413 abgelehnt", async () => {
    const antwort = await starten(
      new Request("http://x/api/uc2/faelle", { method: "POST", headers: { "content-length": "99999", "x-forwarded-for": "10.8.8.9" }, body: "{}" }),
    );
    expect(antwort.status).toBe(413);
  });
});

describe("ohne UC2_MOCK", () => {
  beforeEach(() => vi.stubEnv("UC2_MOCK", ""));

  it("fällt auf den aufgezeichneten Fall zurück, wenn die API nicht erreichbar ist", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("fetch failed"))));
    const antwort = await post({});
    expect(antwort.status).toBe(202);
    expect(((await antwort.json()) as { modus: string }).modus).toBe("vorfuehrung");
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
    expect(strom.headers.get("x-uc2-modus")).toBe("live");
    expect(await strom.text()).toContain("event: ende");
    expect(String(abruf.mock.calls.at(-1)?.[0])).toContain("/faelle/17/ereignisse?seq=4");
  });

  it("GET /api/uc2/modell meldet ohne erreichbare API ebenfalls Testbetrieb, nie einen erfundenen Provider", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("fetch failed"))));
    const body = (await (await modell()).json()) as { provider: string; modell: string };
    expect(body).toMatchObject({ provider: "mock", modell: "mock" });
  });

  it("reicht Fehlerkörper der API nie durch, nur feste einfache Sätze (SEC-009)", async () => {
    const geheim = "Traceback /srv/uc2/api.py line 12 password=hunter2";
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: geheim }), { status: 500 })));
    const start = await post({});
    expect(start.status).toBe(502);
    const text = await start.text();
    expect(text).not.toContain("Traceback");
    expect(text).not.toContain("hunter2");
    expect(JSON.parse(text)).toEqual({ fehler: "Das Panel hat nicht geantwortet. Bitte später noch einmal versuchen." });
    const b = await bericht(new Request("http://x/"), ctx("17"));
    expect(b.status).toBe(502);
    expect(await b.text()).not.toContain("Traceback");
    const l = await liste();
    expect(l.status).toBe(502);
    expect(await l.text()).not.toContain("hunter2");
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: geheim }), { status: 404 })));
    const unbekannt = await bericht(new Request("http://x/"), ctx("99"));
    expect(unbekannt.status).toBe(404);
    expect(await unbekannt.json()).toEqual({ fehler: "Diesen Fall gibt es nicht." });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: geheim }), { status: 422 })));
    expect((await (await post({ provider: "claude" })).json())).toEqual({ fehler: "Das Panel nimmt dieses Modell oder diese Auswahl gerade nicht an." });
  });

  it("gibt bei Erfolg nur fall_id und status der API weiter, keine weiteren Felder", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ fall_id: 5, status: "laeuft", intern: "pfad=/srv" }, { status: 202 })));
    expect(await (await post({})).json()).toEqual({ fall_id: "5", status: "laeuft" });
  });

  it("gibt 409 der API als festen Satz weiter und meldet 502, wenn der Strom eines echten Falls nicht zu erreichen ist", async () => {
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

  it("UC2_START_PROVIDER legt Modell und Belege fest: anderes Modell 422 ohne API-Aufruf, Belege immer fixture", async () => {
    const abruf = vi.fn(async (_u: string | URL | Request, _o?: RequestInit) => Response.json({ fall_id: "3", status: "laeuft" }, { status: 202 }));
    vi.stubGlobal("fetch", abruf);
    const gesendet = () => JSON.parse(String(abruf.mock.calls.at(-1)?.[1]?.body)) as { provider?: string; belege?: string };
    vi.stubEnv("UC2_START_PROVIDER", "azure");
    await post({ akteure: ["sv"], belege: "index" });
    expect(gesendet()).toMatchObject({ provider: "azure", belege: "fixture" });
    expect((await post({ provider: "azure" })).status).toBe(202);
    abruf.mockClear();
    const anders = await post({ provider: "claude" });
    expect(anders.status).toBe(422);
    expect(await anders.json()).toEqual({ fehler: "Hier verhandelt nur das eingestellte Modell." });
    expect(abruf).not.toHaveBeenCalled();
    // Ungültiger Wert zählt wie nicht gesetzt: der Body geht unverändert durch.
    vi.stubEnv("UC2_START_PROVIDER", "gpt");
    await post({ belege: "index" });
    expect(gesendet()).toEqual({ fall: "wartezeiten", belege: "index" });
    vi.stubEnv("UC2_START_PROVIDER", "");
    await post({ provider: "claude" });
    expect(gesendet()).toEqual({ fall: "wartezeiten", provider: "claude" });
  });

  it("Start ohne Antwort in der Frist bei erreichbarer API: 504 mit festem Satz, keine Aufzeichnung", async () => {
    // Fängt den stillen Rückfall: Der Start lief im Hintergrund weiter, die Seite zeigte aber die Aufzeichnung.
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_u: string | URL | Request, o?: RequestInit) =>
        o?.method === "POST" ? Promise.reject(new DOMException("abgebrochen", "AbortError")) : Response.json([]),
      ),
    );
    const antwort = await post({});
    expect(antwort.status).toBe(504);
    const text = await antwort.text();
    expect(JSON.parse(text)).toEqual({ fehler: "Der Start dauert gerade zu lange. Bitte in einer Minute noch einmal versuchen." });
    expect(text).not.toContain("mock-wartezeiten");
  });

  it("503 der API: beim Start ein eigener fester Satz, bei der Liste der allgemeine Satz", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ detail: "limit 3/3" }, { status: 503 })));
    const antwort = await post({});
    expect(antwort.status).toBe(503);
    expect(await antwort.json()).toEqual({ fehler: "Eine neue Live-Verhandlung ist gerade nicht möglich. Die aufgezeichnete Verhandlung bleibt." });
    // GET sieht 503 auch bei fehlender Datenbank: dort kein Satz über Live-Verhandlungen.
    const l = await liste();
    expect(await l.text()).not.toContain("Live-Verhandlung");
    expect(l.status).toBe(502);
  });

  it("Weg der Oberfläche: akteure abgelehnt, der zweite Start bleibt aus, API erreichbar → 504 nach genau zwei POSTs", async () => {
    const abruf = vi.fn(async (_u: string | URL | Request, o?: RequestInit) => {
      if (o?.method !== "POST") return Response.json([]);
      if (String(o.body).includes("akteure")) return new Response("{}", { status: 422 });
      throw new DOMException("abgebrochen", "AbortError");
    });
    vi.stubGlobal("fetch", abruf);
    const antwort = await post({ akteure: ["sv"] });
    expect(antwort.status).toBe(504);
    const text = await antwort.text();
    expect(JSON.parse(text)).toEqual({ fehler: "Der Start dauert gerade zu lange. Bitte in einer Minute noch einmal versuchen." });
    expect(text).not.toContain("mock-wartezeiten");
    expect(abruf.mock.calls.filter((c) => c[1]?.method === "POST")).toHaveLength(2);
  });
});
