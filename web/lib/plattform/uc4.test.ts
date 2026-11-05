import fixture from "../../../shared/schema/fixtures/uc-antwort.json";
import { erstelleRatenlimit, type PruefeRatenlimit } from "./ratenlimit";
import { BUDGET_MELDUNG, frageAntwort, ROUTER_ARGV, standardAusfuehren, type Ausfuehren } from "./uc4";
import { ergebnisSchema, type Ergebnis } from "./uc4-ergebnis";

// Fängt ab: Kette in falscher Reihenfolge, Frage ohne Grenze, ein Router-Fehler als 500 oder halbe Daten,
// Mock-Schalter ohne Wirkung, eine Frage, die als Schalter des Routers gelesen wird, und „keine Antwort“
// (Exit 1) als Fehler statt als Ergebnis; ein Ratenlimit ohne Wirkung auf die Route und ein erschöpftes
// Tagesbudget (Exit 3) als 502 statt 429.

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
    for (const body of [{ frage: "   " }, { frage: "a".repeat(501) }, {}, "kein json"]) {
      const antwort = await frageAntwort(anfrage(body), { ausfuehren, umgebung: {}, wurzel: () => "/r", ratenlimit: offen });
      expect(antwort.status).toBe(400);
      expect(typeof (await antwort.json()).fehler).toBe("string");
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

describe("POST /api/uc4/frage, Ratenlimit und Tagesbudget (#100)", () => {
  it("das Ratenlimit greift vor dem Subprozess", async () => {
    const ausfuehren = liefert(JSON.stringify(ergebnis));
    const ratenlimit = erstelleRatenlimit({ proMinute: 1 });
    const optionen = { ausfuehren, umgebung: {}, wurzel: () => "/r", ratenlimit, jetzt: () => 0 };
    expect((await frageAntwort(anfrage({ frage: "x" }), optionen)).status).toBe(200);
    expect((await frageAntwort(anfrage({ frage: "x" }), optionen)).status).toBe(429);
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
