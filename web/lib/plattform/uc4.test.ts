import fixture from "../../../shared/schema/fixtures/uc-antwort.json";
import { erstelleRatenlimit, type PruefeRatenlimit } from "./ratenlimit";
import {
  BUDGET_MELDUNG,
  erstelleFrageAntwort,
  ROUTER_ARGV,
  standardAusfuehren,
  type Ausfuehren,
  type FrageOptionen,
} from "./uc4";
import { ergebnisSchema, type Ergebnis } from "./uc4-ergebnis";

// Fängt ab: Kette in falscher Reihenfolge, Frage ohne Grenze, ein Router-Fehler als 500 oder halbe Daten,
// Mock-Schalter ohne Wirkung, eine Frage, die als Schalter des Routers gelesen wird, und „keine Antwort“
// (Exit 1) als Fehler statt als Ergebnis. Dazu die zweite Sperre hinter dem Proxy: Online-Demo nur lesend,
// zu großer Body, mehr als zwei Läufe gleichzeitig und ein Slot, der nach einem Fehler belegt bleibt. Aus #100: ein
// Ratenlimit ohne Wirkung auf die Route oder erst nach dem Body-Lesen, und ein erschöpftes Tagesbudget (Exit 3)
// als 502 statt 429.

/** Ein frischer Handler je Aufruf, damit die Lauf-Zählung eines Tests keinen anderen berührt. */
const frageAntwort = (a: Request, optionen: FrageOptionen) => erstelleFrageAntwort(optionen)(a);

const ergebnis: Ergebnis = {
  antworten: [
    fixture as Ergebnis["antworten"][number],
    { ...(fixture as Ergebnis["antworten"][number]), uc: "uc2", modell: "mock", text: "Position des Panels." },
    { text: "Einfach erklärt.", belege: [], zahlen: [], uc: "uc1", modell: "mock", protokoll_id: null },
  ],
  fehlend: [],
};

function anfrage(body: unknown): Request {
  return new Request("http://lokal/api/uc4/frage", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

/** Kein Limit: die übrigen Fälle prüfen die Route, nicht das Ratenlimit. */
const offen: PruefeRatenlimit = () => null;

const liefert = (stdout: string, code = 0) => vi.fn<Ausfuehren>(async () => ({ code, stdout }));

beforeEach(() => {
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

describe("POST /api/uc4/frage", () => {
  it("liefert 200 mit den Antworten in Kettenreihenfolge und ruft uv in der Repo-Wurzel", async () => {
    const ausfuehren = liefert(JSON.stringify(ergebnis));
    const antwort = await frageAntwort(anfrage({ frage: "  Wie viele Beschäftigte gab es 2025-03?  " }), {
      ausfuehren,
      umgebung: {},
      wurzel: () => "/repo",
      ratenlimit: offen,
    });

    expect(antwort.status).toBe(200);
    const daten = ergebnisSchema.parse(await antwort.json());
    expect(daten.antworten.map((a) => a.uc)).toEqual(["uc3", "uc2", "uc1"]);
    expect(ausfuehren).toHaveBeenCalledWith("uv", [...ROUTER_ARGV, "--", "Wie viele Beschäftigte gab es 2025-03?"], {
      cwd: "/repo",
      timeout: 60_000,
      maxBuffer: 1024 * 1024,
    });
  });

  it("UC4_ADAPTER=mock hängt --mock an, eine Frage mit Bindestrich bleibt nach -- ein Argument", async () => {
    const ausfuehren = liefert(JSON.stringify(ergebnis));
    await frageAntwort(anfrage({ frage: "-h" }), { ausfuehren, umgebung: { UC4_ADAPTER: "mock" }, wurzel: () => "/r", ratenlimit: offen });
    expect(ausfuehren.mock.calls[0]?.[1]).toEqual([...ROUTER_ARGV, "--mock", "--", "-h"]);
  });

  it("Exit 1 mit allen UCs fehlend ist ein Ergebnis, kein Fehler", async () => {
    const leer: Ergebnis = {
      antworten: [],
      fehlend: [
        { uc: "uc3", grund: "kein_adapter" },
        { uc: "uc2", grund: "kein_adapter" },
        { uc: "uc1", grund: "TimeoutError" },
      ],
    };
    const antwort = await frageAntwort(anfrage({ frage: "x" }), { ausfuehren: liefert(JSON.stringify(leer), 1), umgebung: {}, wurzel: () => "/r", ratenlimit: offen });
    expect(antwort.status).toBe(200);
    expect(await antwort.json()).toEqual(leer);
  });

  it("weist eine leere, zu lange oder fehlende Frage mit 400 ab, ohne den Router zu starten", async () => {
    const ausfuehren = liefert(JSON.stringify(ergebnis));
    const faelle: Array<[unknown, string]> = [
      [{ frage: "   " }, "Bitte eine Frage eingeben."],
      [{ frage: "a".repeat(501) }, "Höchstens 500 Zeichen."],
      [{}, "Die Anfrage braucht JSON mit dem Feld frage als Text."],
      [{ frage: 1 }, "Die Anfrage braucht JSON mit dem Feld frage als Text."],
      ["null", "Die Anfrage braucht JSON mit dem Feld frage als Text."],
      ["kein json", "Die Anfrage braucht JSON mit dem Feld frage als Text."],
    ];
    for (const [body, meldung] of faelle) {
      const antwort = await frageAntwort(anfrage(body), { ausfuehren, umgebung: {}, wurzel: () => "/r" });
      expect(antwort.status).toBe(400);
      expect((await antwort.json()).fehler).toBe(meldung);
    }
    expect(ausfuehren).not.toHaveBeenCalled();
  });

  it("liefert 502 mit Meldung bei Timeout, fremdem Exit-Code, kaputtem JSON und Vertragsbruch", async () => {
    const fehlerfaelle: Ausfuehren[] = [
      vi.fn<Ausfuehren>(async () => {
        throw Object.assign(new Error("timeout"), { name: "TimeoutError" });
      }),
      liefert("", 2),
      liefert("Traceback (most recent call last)"),
      liefert(JSON.stringify({ ...ergebnis, fehlend: ["uc1"] })),
    ];
    for (const ausfuehren of fehlerfaelle) {
      const antwort = await frageAntwort(anfrage({ frage: "x" }), { ausfuehren, umgebung: {}, wurzel: () => "/r", ratenlimit: offen });
      expect(antwort.status).toBe(502);
      expect((await antwort.json()).fehler).toMatch(/Kette/);
    }
  });
});

describe("Sperren vor dem Subprozess", () => {
  it("KIC_ONLINE_LESEND=1 liefert 403 ohne Subprozess", async () => {
    const ausfuehren = liefert(JSON.stringify(ergebnis));
    const antwort = await frageAntwort(anfrage({ frage: "x" }), { ausfuehren, umgebung: { KIC_ONLINE_LESEND: "1" }, wurzel: () => "/r" });
    expect(antwort.status).toBe(403);
    expect(ausfuehren).not.toHaveBeenCalled();
  });

  it("ein Body über 4 KiB liefert 413, per Content-Length und beim Lesen ohne Angabe", async () => {
    const ausfuehren = liefert(JSON.stringify(ergebnis));
    const gross = JSON.stringify({ frage: "a".repeat(5000) });
    const ohneLaenge = new Request("http://lokal/api/uc4/frage", {
      method: "POST",
      body: new ReadableStream({
        start(strom) {
          strom.enqueue(new TextEncoder().encode(gross));
          strom.close();
        },
      }),
      duplex: "half",
    } as RequestInit);
    expect(ohneLaenge.headers.get("content-length")).toBeNull();
    for (const a of [anfrage(gross), ohneLaenge]) {
      expect((await frageAntwort(a, { ausfuehren, umgebung: {}, wurzel: () => "/r" })).status).toBe(413);
    }
    expect(ausfuehren).not.toHaveBeenCalled();
  });

  it("der dritte gleichzeitige Lauf bekommt 429, ein Slot wird auch nach einem Fehler frei", async () => {
    const offen: Array<(lauf: { code: number; stdout: string }) => void> = [];
    let wirft = false;
    const ausfuehren = vi.fn<Ausfuehren>(() => {
      if (wirft) return Promise.reject(new Error("kaputt"));
      return new Promise((aufloesen) => offen.push(aufloesen));
    });
    const frage = erstelleFrageAntwort({ ausfuehren, umgebung: {}, wurzel: () => "/r" });

    const erste = frage(anfrage({ frage: "a" }));
    const zweite = frage(anfrage({ frage: "b" }));
    await vi.waitFor(() => expect(offen).toHaveLength(2));
    expect((await frage(anfrage({ frage: "c" }))).status).toBe(429);

    offen[0]!({ code: 0, stdout: "kaputt" }); // Vertragsbruch: 502, Slot muss trotzdem frei werden
    expect((await erste).status).toBe(502);
    wirft = true;
    expect((await frage(anfrage({ frage: "d" }))).status).toBe(502); // Subprozess wirft, Slot wieder frei
    wirft = false;
    const dritte = frage(anfrage({ frage: "e" }));
    await vi.waitFor(() => expect(offen).toHaveLength(3));
    offen[1]!({ code: 0, stdout: JSON.stringify(ergebnis) });
    offen[2]!({ code: 0, stdout: JSON.stringify(ergebnis) });
    expect([(await zweite).status, (await dritte).status]).toEqual([200, 200]);
    expect(ausfuehren).toHaveBeenCalledTimes(4);
  });
});

describe("POST /api/uc4/frage, Ratenlimit und Tagesbudget (#100)", () => {
  it("das Ratenlimit greift vor Body-Lesen und Subprozess", async () => {
    const ausfuehren = liefert(JSON.stringify(ergebnis));
    const ratenlimit = erstelleRatenlimit({ proMinute: 1 });
    const optionen = { ausfuehren, umgebung: {}, wurzel: () => "/r", ratenlimit, jetzt: () => 0 };
    expect((await frageAntwort(anfrage({ frage: "x" }), optionen)).status).toBe(200);
    // Ein zu großer Body wäre 413; das Limit kommt vorher.
    const gesperrt = await frageAntwort(anfrage({ frage: "a".repeat(5000) }), optionen);
    expect(gesperrt.status).toBe(429);
    expect(gesperrt.headers.get("retry-after")).toBe("60");
    expect(ausfuehren).toHaveBeenCalledTimes(1);
  });

  it("Exit 3 mit fehler budget_erschoepft wird 429 mit Hinweis und Retry-After bis Mitternacht UTC", async () => {
    const stdout = JSON.stringify({ fehler: "budget_erschoepft", meldung: "…" });
    const antwort = await frageAntwort(anfrage({ frage: "x" }), {
      ausfuehren: liefert(stdout, 3),
      umgebung: {},
      wurzel: () => "/r",
      ratenlimit: offen,
      jetzt: () => Date.UTC(2026, 10, 5, 23, 0, 0),
    });
    expect(antwort.status).toBe(429);
    expect(antwort.headers.get("retry-after")).toBe("3600");
    expect(await antwort.json()).toEqual({ fehler: BUDGET_MELDUNG });
  });
});

describe("standardAusfuehren", () => {
  it("liefert stdout auch bei Exit 1 und wirft beim Timeout", async () => {
    const optionen = { cwd: process.cwd(), timeout: 10_000, maxBuffer: 64 * 1024 };
    expect(await standardAusfuehren(process.execPath, ["-e", "console.log('{}'); process.exit(1)"], optionen)).toEqual({
      code: 1,
      stdout: "{}\n",
    });
    await expect(
      standardAusfuehren(process.execPath, ["-e", "setTimeout(() => {}, 5000)"], { ...optionen, timeout: 200 }),
    ).rejects.toThrow();
  });
});

// Fängt ab (Modellwahl auf /uc4, Lead c0): das gewählte Modell kommt nicht beim Router an, ein beliebiger Wert
// gelangt als LLM_PROVIDER in den Subprozess, oder ohne Wahl wird die Einstellung der App überschrieben.
describe("POST /api/uc4/frage, Modellwahl", () => {
  const optionen = (ausfuehren: Ausfuehren): FrageOptionen => ({ ausfuehren, umgebung: {}, wurzel: () => "/repo", ratenlimit: offen });

  it("reicht die Wahl als LLM_PROVIDER nur an diesen Lauf weiter", async () => {
    const ausfuehren = liefert(JSON.stringify(ergebnis));
    const antwort = await frageAntwort(anfrage({ frage: "Wie viele?", modell: "mistral" }), optionen(ausfuehren));
    expect(antwort.status).toBe(200);
    expect(ausfuehren.mock.calls[0]?.[2].zusatz).toEqual({ LLM_PROVIDER: "mistral" });
  });

  it("Testbetrieb nimmt die festen Antworten des Routers (--mock)", async () => {
    const ausfuehren = liefert(JSON.stringify(ergebnis));
    await frageAntwort(anfrage({ frage: "Wie viele?", modell: "mock" }), optionen(ausfuehren));
    expect(ausfuehren.mock.calls[0]?.[1]).toEqual([...ROUTER_ARGV, "--mock", "--", "Wie viele?"]);
    expect(ausfuehren.mock.calls[0]?.[2].zusatz).toEqual({ LLM_PROVIDER: "mock" });
  });

  it("ohne Wahl bleibt die Einstellung der App", async () => {
    const ausfuehren = liefert(JSON.stringify(ergebnis));
    await frageAntwort(anfrage({ frage: "Wie viele?" }), optionen(ausfuehren));
    expect(ausfuehren.mock.calls[0]?.[2].zusatz).toBeUndefined();
  });

  it("lehnt ein unbekanntes Modell mit 400 ab, ohne Subprozess", async () => {
    const ausfuehren = liefert(JSON.stringify(ergebnis));
    const antwort = await frageAntwort(anfrage({ frage: "Wie viele?", modell: "gpt; rm -rf" }), optionen(ausfuehren));
    expect(antwort.status).toBe(400);
    expect(await antwort.json()).toEqual({ fehler: "Dieses Modell gibt es hier nicht." });
    expect(ausfuehren).not.toHaveBeenCalled();
  });
});
