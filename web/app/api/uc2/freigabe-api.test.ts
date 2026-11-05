import { NAME_UNGUELTIG, POST as freigeben } from "./faelle/[id]/freigabe/route";

// POST /api/uc2/faelle/{id}/freigabe: Sperren vor dem Body, Prüfung des Namens, Durchreichen an die Python-API mit festen
// Sätzen, Vorführmodus ohne Speichern. Namen sind erfunden ("Musterfrau" lehnt die Namensregel selbst ab).

const ctx = (id: string) => ({ params: Promise.resolve({ id }) });
let nummer = 0;
// Jede Anfrage kommt von einer eigenen IP, damit das Ratenlimit (10 je Minute und IP) die Tests nicht stört.
const post = (id: string, body: unknown, { roh, ip }: { roh?: string; ip?: string } = {}) =>
  freigeben(
    new Request(`http://x/api/uc2/faelle/${id}/freigabe`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-forwarded-for": ip ?? `10.1.0.${++nummer}` },
      body: roh ?? JSON.stringify(body),
    }),
    ctx(id),
  );
const gut = { name: "Maria Beispiel", entscheidung: "freigegeben" };

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

it("sperrt in der Online-Demo mit 403, bevor der Body gelesen wird", async () => {
  vi.stubEnv("KIC_ONLINE_LESEND", "1");
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  // Der Körper ist weder JSON noch klein; die Sperre greift davor, sonst gäbe es 400 oder 413.
  const antwort = await post("42", null, { roh: "x".repeat(10_000) });
  expect(antwort.status).toBe(403);
  expect(await antwort.json()).toEqual({ fehler: "Freigeben ist in der Online-Demo gesperrt." });
  expect(fetchMock).not.toHaveBeenCalled();
});

it("drosselt je IP mit 429", async () => {
  vi.stubEnv("UC2_MOCK", "1");
  const ip = "10.9.9.9";
  const status: number[] = [];
  for (let i = 0; i < 11; i++) status.push((await post("mock-wartezeiten", gut, { ip })).status);
  expect(status.slice(0, 10)).toEqual(Array(10).fill(200));
  expect(status[10]).toBe(429);
});

it("lehnt einen zu großen Body mit 413 ab, auch ohne Content-Length", async () => {
  expect((await post("42", null, { roh: JSON.stringify({ ...gut, begruendung: "x".repeat(5000) }) })).status).toBe(413);
  const strom = new ReadableStream<Uint8Array>({
    start(s) {
      s.enqueue(new TextEncoder().encode("{" + " ".repeat(5000)));
      s.close();
    },
  });
  const antwort = await freigeben(
    new Request("http://x/api/uc2/faelle/42/freigabe", {
      method: "POST",
      body: strom,
      headers: { "x-forwarded-for": "10.2.0.1" },
      duplex: "half",
    } as RequestInit),
    ctx("42"),
  );
  expect(antwort.status).toBe(413);
});

it("lehnt ungültige Anfragen ab: kein JSON, falsche Felder, Team, Ablehnung ohne Begründung", async () => {
  expect((await post("42", null, { roh: "nicht json" })).status).toBe(400);
  expect((await post("42", { name: "Maria Beispiel", entscheidung: "vielleicht" })).status).toBe(400);
  const team = await post("42", { name: "Team", entscheidung: "freigegeben" });
  expect(team.status).toBe(422);
  expect(await team.json()).toEqual({ fehler: NAME_UNGUELTIG });
  expect((await post("42", { name: "Das Team", entscheidung: "freigegeben" })).status).toBe(422);
  expect((await post("42", { name: "Maria Beispiel", entscheidung: "abgelehnt" })).status).toBe(422);
  expect((await post("../x", gut)).status).toBe(400);
});

it("im Vorführmodus wird nichts gespeichert und die API nicht gerufen", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const antwort = await post("mock-wartezeiten", gut);
  expect(antwort.status).toBe(200);
  expect(antwort.headers.get("x-uc2-modus")).toBe("vorfuehrung");
  expect(await antwort.json()).toMatchObject({ gespeichert: false });
  expect(fetchMock).not.toHaveBeenCalled();
});

it("reicht echte Fälle an die Python-API durch und gibt die Zeit zurück", async () => {
  const fetchMock = vi.fn(async () => Response.json({ zeitpunkt: "2026-11-05T16:30:00+00:00" }));
  vi.stubGlobal("fetch", fetchMock);
  const antwort = await post("42", { ...gut, name: "  Maria   Beispiel " });
  expect(antwort.status).toBe(200);
  expect(await antwort.json()).toEqual({ zeitpunkt: "2026-11-05T16:30:00+00:00", gespeichert: true });
  const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toBe("http://localhost:8102/faelle/42/freigabe");
  expect(init.method).toBe("POST");
  expect(JSON.parse(init.body as string)).toEqual({ name: "Maria Beispiel", entscheidung: "freigegeben" });
});

it("zeigt Fehler der API nur als feste Sätze, nie ihren Körper", async () => {
  const geheim = "Traceback /srv/geheim/pfad.py SELECT * FROM uc2.fall";
  for (const [status, erwartet] of [
    [403, 403],
    [404, 404],
    [409, 409],
    [422, 422],
    [429, 429],
    [500, 502],
  ] as const) {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ detail: geheim }, { status })));
    const antwort = await post("42", gut);
    expect(antwort.status).toBe(erwartet);
    expect(JSON.stringify(await antwort.json())).not.toContain("geheim");
  }
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({ unerwartet: true })));
  expect((await post("42", gut)).status).toBe(502);
  vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("ECONNREFUSED"); }));
  expect((await post("42", gut)).status).toBe(502);
});

it("kennt für echte Fälle nur Nummern", async () => {
  vi.stubGlobal("fetch", vi.fn());
  expect((await post("abc", gut)).status).toBe(404);
});
