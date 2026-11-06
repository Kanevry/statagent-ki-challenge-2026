import fixture from "../../../shared/schema/fixtures/uc-antwort.json";
import { erstelleRatenlimit, type PruefeRatenlimit } from "./ratenlimit";
import {
  BUDGET_MELDUNG,
  DECKEL_MELDUNG,
  erstelleFrageAntwort,
  STATION_FRAGEN_PRO_TAG,
  STATION_PRO_MINUTE,
  ROUTER_ARGV,
  standardAusfuehren,
  standardStromStarten,
  modellErlaubt,
  uc4Einstellung,
  type Ausfuehren,
  type StromStarten,
  type FrageOptionen,
} from "./uc4";
import { BUDGET_MELDUNG as BUDGET_TEXT, ergebnisSchema, stromEreignisSchema, type Ergebnis } from "./uc4-ergebnis";

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
      timeout: 180_000,
      maxBuffer: 1024 * 1024,
      signal: expect.any(AbortSignal),
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

// Fängt ab (Modellwahl auf /uc4, Lead): das gewählte Modell kommt nicht beim Router an, ein beliebiger Wert
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

  // Fängt ab (Review !72, Geld): online hebelte die Wahl LLM_PROVIDER=mock des Compose aus und rief bezahlte Anbieter.
  it("online (KIC_ONLINE=1) nur Testbetrieb und die Anbieter aus UC4_MODELLWAHL", async () => {
    const ausfuehren = liefert(JSON.stringify(ergebnis));
    const online = (modell: string, liste?: string) =>
      frageAntwort(anfrage({ frage: "Wie viele?", modell }), {
        ausfuehren,
        // Stufe B: volle Kette ausdrücklich, sonst gilt online nur UC3 und die Wahl wirkt gar nicht
        umgebung: { KIC_ONLINE: "1", UC4_KETTE: "uc3,uc2,uc1", ...(liste === undefined ? {} : { UC4_MODELLWAHL: liste }) },
        wurzel: () => "/repo",
        ratenlimit: offen,
      });
    const claude = await online("claude");
    expect(claude.status).toBe(400);
    expect(await claude.json()).toEqual({ fehler: "Dieses Modell ist hier nicht freigegeben." });
    expect(ausfuehren).not.toHaveBeenCalled();
    expect((await online("mock")).status).toBe(200);
    expect((await online("azure", "azure, mistral")).status).toBe(200);
    expect((await online("claude", "azure, mistral")).status).toBe(400);
    expect(ausfuehren).toHaveBeenCalledTimes(2);
  });

  it("lehnt ein unbekanntes Modell mit 400 ab, ohne Subprozess", async () => {
    const ausfuehren = liefert(JSON.stringify(ergebnis));
    const antwort = await frageAntwort(anfrage({ frage: "Wie viele?", modell: "gpt; rm -rf" }), optionen(ausfuehren));
    expect(antwort.status).toBe(400);
    expect(await antwort.json()).toEqual({ fehler: "Dieses Modell gibt es hier nicht." });
    expect(ausfuehren).not.toHaveBeenCalled();
  });
});

// Online-Demo Stufe A (Lead, 05.11.): Fragen offen, aber ohne Modell, nur UC3. Fängt ab: Fragen bleiben trotz
// KIC_ONLINE_FRAGEN gesperrt, UC2/UC1 laufen online mit Mock-Texten mit, „Testbetrieb“ ersetzt die echte UC3-Zahl
// durch die Mock-Zahl, ein Tippfehler in UC4_KETTE öffnet die volle Kette mit Modellaufrufen.
describe("POST /api/uc4/frage, Online-Stufe A", () => {
  const stufeA = { KIC_ONLINE: "1", KIC_ONLINE_LESEND: "1", KIC_ONLINE_FRAGEN: "1", UC4_KETTE: "uc3" };
  const mitUmgebung = (ausfuehren: Ausfuehren, umgebung: Record<string, string>): FrageOptionen => ({
    ausfuehren,
    umgebung,
    wurzel: () => "/repo",
    ratenlimit: offen,
  });

  it("KIC_ONLINE_FRAGEN=1 öffnet Fragen trotz KIC_ONLINE_LESEND=1 und fragt nur UC3, ohne Modellwahl", async () => {
    const ausfuehren = liefert(JSON.stringify({ antworten: [ergebnis.antworten[0]], fehlend: [] }));
    const antwort = await frageAntwort(anfrage({ frage: "Wie viele?", modell: "mock" }), mitUmgebung(ausfuehren, stufeA));
    expect(antwort.status).toBe(200);
    expect(ausfuehren.mock.calls[0]?.[1]).toEqual([...ROUTER_ARGV, "--kette", "uc3", "--", "Wie viele?"]);
    expect(ausfuehren.mock.calls[0]?.[2].zusatz).toBeUndefined();
  });

  it("ohne Modell in der Kette wird auch ein nicht freigegebenes Modell nicht abgelehnt, sondern ignoriert", async () => {
    const ausfuehren = liefert(JSON.stringify({ antworten: [ergebnis.antworten[0]], fehlend: [] }));
    const antwort = await frageAntwort(anfrage({ frage: "Wie viele?", modell: "claude" }), mitUmgebung(ausfuehren, stufeA));
    expect(antwort.status).toBe(200);
    expect(ausfuehren.mock.calls[0]?.[2].zusatz).toBeUndefined();
  });

  it("ein ungültiger Wert in UC4_KETTE fällt auf nur UC3 zurück", async () => {
    const ausfuehren = liefert(JSON.stringify({ antworten: [ergebnis.antworten[0]], fehlend: [] }));
    await frageAntwort(anfrage({ frage: "Wie viele?" }), mitUmgebung(ausfuehren, { UC4_KETTE: "uc3,uc9" }));
    expect(ausfuehren.mock.calls[0]?.[1]).toEqual([...ROUTER_ARGV, "--kette", "uc3", "--", "Wie viele?"]);
  });

  it("UC4_KETTE hält die Standardreihenfolge, leer heißt volle Kette ohne --kette", async () => {
    const ausfuehren = liefert(JSON.stringify(ergebnis));
    await frageAntwort(anfrage({ frage: "x" }), mitUmgebung(ausfuehren, { UC4_KETTE: "uc1, uc3" }));
    await frageAntwort(anfrage({ frage: "x" }), mitUmgebung(ausfuehren, {}));
    expect(ausfuehren.mock.calls[0]?.[1]).toEqual([...ROUTER_ARGV, "--kette", "uc3,uc1", "--", "x"]);
    expect(ausfuehren.mock.calls[1]?.[1]).toEqual([...ROUTER_ARGV, "--", "x"]);
  });

  it("online (KIC_ONLINE=1) heißt ein leeres UC4_KETTE nur UC3, nicht die volle Kette", async () => {
    const ausfuehren = liefert(JSON.stringify({ antworten: [ergebnis.antworten[0]], fehlend: [] }));
    await frageAntwort(anfrage({ frage: "x" }), mitUmgebung(ausfuehren, { KIC_ONLINE: "1", UC4_KETTE: " " }));
    expect(ausfuehren.mock.calls[0]?.[1]).toEqual([...ROUTER_ARGV, "--kette", "uc3", "--", "x"]);
    expect(uc4Einstellung({ KIC_ONLINE: "1", UC4_KETTE: "uc3,uc2,uc1" }).kette).toEqual(["uc3", "uc2", "uc1"]);
  });

  it("uc4Einstellung sagt der Seite Kette, ob Fragen offen sind und ob ein Modell läuft", () => {
    expect(uc4Einstellung(stufeA)).toMatchObject({ kette: ["uc3"], fragenOffen: true, mitModell: false });
    expect(uc4Einstellung({ KIC_ONLINE_LESEND: "1" })).toMatchObject({
      kette: ["uc3", "uc2", "uc1"],
      fragenOffen: false,
      mitModell: true,
    });
  });

  it("uc4Einstellung bietet online nur an, was der Server annimmt", () => {
    // Fängt Mistral und Claude auf der öffentlichen Seite: wählbar, dann Fehler 400 (online gemessen 06.11.).
    // Und ohne Testbetrieb: Ein Klick zeigte der Jury eine erfundene Zahl (UI-Regie 06.11.).
    expect(uc4Einstellung({ KIC_ONLINE: "1", UC4_MODELLWAHL: "azure" }).modellwahl).toEqual(["azure"]);
    expect(uc4Einstellung({ KIC_ONLINE: "1" }).modellwahl).toEqual([]);
    expect(uc4Einstellung({}).modellwahl).toEqual(["azure", "mistral", "claude", "mock"]);
    for (const modell of uc4Einstellung({ KIC_ONLINE: "1", UC4_MODELLWAHL: "azure" }).modellwahl) {
      expect(modellErlaubt(modell, { KIC_ONLINE: "1", UC4_MODELLWAHL: "azure" })).toBe(true);
    }
  });
});

// Stationen-Strom (Sichtprüfung): Fängt ab: Strom ohne Accept-Header, Status vor der ersten Zeile falsch, eine
// kaputte Zeile, die ungeprüft an die Seite geht, ein Abbruch ohne Schlusszeile, ein Slot, der nach dem Strom oder
// nach einem Abbruch des Clients belegt bleibt, und ein erschöpftes Budget als 200.
describe("POST /api/uc4/frage, Strom der Stationen", () => {
  const ANTWORT = ergebnis.antworten[0];
  const zeilen = {
    start: JSON.stringify({ art: "start", kette: ["uc3", "uc2", "uc1"] }),
    station: JSON.stringify({ art: "station", uc: "uc3", stufe: 1, zustand: "laeuft" }),
    antwort: JSON.stringify({ art: "antwort", uc: "uc3", stufe: 1, dauer_ms: 1073, kern: "7.498.", antwort: ANTWORT }),
    ende: JSON.stringify({ art: "ende", fehlend: [], dauer_ms: 1100 }),
  };

  function stromAus(ausgabe: string[], code: number | null = 0) {
    const abbrechen = vi.fn();
    const starten = vi.fn<StromStarten>(() => ({
      zeilen: (async function* () {
        for (const z of ausgabe) yield z;
      })(),
      ende: Promise.resolve(code),
      abbrechen,
    }));
    return { starten, abbrechen };
  }

  function stromAnfrage(body: unknown): Request {
    return new Request("http://lokal/api/uc4/frage", {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/x-ndjson" },
      body: JSON.stringify(body),
    });
  }

  async function lies(antwort: Response) {
    const text = await antwort.text();
    return text
      .split("\n")
      .filter((z) => z !== "")
      .map((z) => stromEreignisSchema.parse(JSON.parse(z)));
  }

  const optionen = (stromStarten: StromStarten, extra: Partial<FrageOptionen> = {}): FrageOptionen => ({
    stromStarten,
    umgebung: {},
    wurzel: () => "/repo",
    ratenlimit: offen,
    ...extra,
  });

  it("liefert jede Zeile geprüft als NDJSON, mit --strom und dem gewählten Modell im Start", async () => {
    const { starten } = stromAus([zeilen.start, zeilen.station, zeilen.antwort, zeilen.ende]);
    const antwort = await frageAntwort(stromAnfrage({ frage: "Wie viele?", modell: "azure" }), optionen(starten));
    expect(antwort.status).toBe(200);
    expect(antwort.headers.get("content-type")).toBe("application/x-ndjson; charset=utf-8");
    const ereignisse = await lies(antwort);
    expect(ereignisse.map((e) => e.art)).toEqual(["start", "station", "antwort", "ende"]);
    expect(ereignisse[0]).toEqual({ art: "start", kette: ["uc3", "uc2", "uc1"], modell: "azure" });
    expect(starten.mock.calls[0]?.[1]).toEqual([...ROUTER_ARGV, "--strom", "--", "Wie viele?"]);
    expect(starten.mock.calls[0]?.[2].zusatz).toEqual({ LLM_PROVIDER: "azure" });
  });

  it("ohne Accept-Header bleibt die Antwort das Ergebnis am Ende (kein Strom)", async () => {
    const ausfuehren = liefert(JSON.stringify(ergebnis));
    const { starten } = stromAus([]);
    const antwort = await frageAntwort(anfrage({ frage: "x" }), { ...optionen(starten), ausfuehren });
    expect(antwort.headers.get("content-type")).toContain("application/json");
    expect(starten).not.toHaveBeenCalled();
  });

  it("eine kaputte Zeile mitten im Strom endet mit einer fehler-Zeile und bricht den Router ab", async () => {
    const { starten, abbrechen } = stromAus([zeilen.start, '{"art":"antwort","uc":"uc9"}', zeilen.ende]);
    const ereignisse = await lies(await frageAntwort(stromAnfrage({ frage: "x" }), optionen(starten)));
    expect(ereignisse.at(-1)).toEqual({ art: "fehler", fehler: "Die Kette hat in einem unerwarteten Format geantwortet." });
    expect(abbrechen).toHaveBeenCalled();
  });

  it("ein Ende ohne Abschluss (Timeout) bekommt eine fehler-Zeile", async () => {
    const { starten } = stromAus([zeilen.start, zeilen.station], null);
    const ereignisse = await lies(await frageAntwort(stromAnfrage({ frage: "x" }), optionen(starten)));
    expect(ereignisse.at(-1)).toEqual({ art: "fehler", fehler: "Die Kette hat nicht rechtzeitig geantwortet." });
  });

  it("erschöpftes Budget in der ersten Zeile wird 429 mit Retry-After, kein Strom", async () => {
    const budget = JSON.stringify({ art: "fehler", fehler: "budget_erschoepft", meldung: "aufgebraucht" });
    const { starten } = stromAus([budget], 3);
    const antwort = await frageAntwort(stromAnfrage({ frage: "x" }), optionen(starten));
    expect(antwort.status).toBe(429);
    expect(await antwort.json()).toEqual({ fehler: BUDGET_TEXT });
    expect(antwort.headers.get("retry-after")).toMatch(/^[1-9][0-9]*$/);
  });

  it("keine gültige erste Zeile wird 502", async () => {
    const { starten } = stromAus(["kein json"], 0);
    expect((await frageAntwort(stromAnfrage({ frage: "x" }), optionen(starten))).status).toBe(502);
  });

  it("gibt den Slot nach dem Strom und nach einem Abbruch des Clients wieder frei", async () => {
    const { starten, abbrechen } = stromAus([zeilen.start, zeilen.station, zeilen.antwort, zeilen.ende]);
    const handler = erstelleFrageAntwort(optionen(starten, { maxLaeufe: 1 }));
    await (await handler(stromAnfrage({ frage: "x" }))).text();
    const zweite = await handler(stromAnfrage({ frage: "x" }));
    expect(zweite.status).toBe(200);
    await zweite.body?.cancel();
    expect(abbrechen).toHaveBeenCalled();
    expect((await handler(stromAnfrage({ frage: "x" }))).status).toBe(200);
  });

  it("EOF ohne ende-Zeile bei Exit 1 endet mit einer fehler-Zeile (Seite bleibt nicht auf „läuft“)", async () => {
    const { starten } = stromAus([zeilen.start, zeilen.station], 1);
    const ereignisse = await lies(await frageAntwort(stromAnfrage({ frage: "x" }), optionen(starten)));
    expect(ereignisse.at(-1)).toEqual({ art: "fehler", fehler: "Die Kette ist mit einem Fehler abgebrochen." });
  });

  it("ein Lesefehler der Pipe beendet den Router, schreibt fehler und gibt den Slot frei", async () => {
    const abbrechen = vi.fn();
    const starten = vi.fn<StromStarten>(() => ({
      zeilen: (async function* () {
        yield zeilen.start;
        throw new Error("EPIPE");
      })(),
      ende: Promise.resolve(null),
      abbrechen,
    }));
    const handler = erstelleFrageAntwort(optionen(starten, { maxLaeufe: 1 }));
    const ereignisse = await lies(await handler(stromAnfrage({ frage: "x" })));
    expect(ereignisse.at(-1)).toEqual({ art: "fehler", fehler: "Die Kette ist mit einem Fehler abgebrochen." });
    expect(abbrechen).toHaveBeenCalled();
    expect((await handler(stromAnfrage({ frage: "x" }))).status).toBe(200);
  });

  it("bricht der Client vor der ersten Zeile ab, endet der Router und der Slot wird frei", async () => {
    let weiter: () => void = () => {};
    let ende: (code: number | null) => void = () => {};
    const abbrechen = vi.fn(() => {
      weiter();
      ende(null);
    });
    const haengt = {
      // Hängt bis zum Abbruch und endet dann ohne eine einzige Zeile (das leere yield* hält require-yield ein).
      zeilen: (async function* () {
        await new Promise<void>((los) => (weiter = los));
        yield* [];
      })(),
      ende: new Promise<number | null>((aufloesen) => (ende = aufloesen)),
      abbrechen,
    };
    const normal = stromAus([zeilen.start, zeilen.ende]);
    const starten = vi.fn<StromStarten>().mockReturnValueOnce(haengt).mockImplementation(normal.starten);
    const handler = erstelleFrageAntwort(optionen(starten, { maxLaeufe: 1 }));
    const steuerung = new AbortController();
    const antwort = handler(new Request(stromAnfrage({ frage: "x" }), { signal: steuerung.signal }));
    await vi.waitFor(() => expect(starten).toHaveBeenCalledTimes(1));
    steuerung.abort();
    expect((await antwort).status).toBe(502);
    expect(abbrechen).toHaveBeenCalled();
    expect((await handler(stromAnfrage({ frage: "x" }))).status).toBe(200);
  });

  it("nach der ende-Zeile meldet ein Exit ungleich 0/1 trotzdem einen Fehler (#150)", async () => {
    const { starten } = stromAus([zeilen.start, zeilen.ende], 2);
    const ereignisse = await lies(await frageAntwort(stromAnfrage({ frage: "x" }), optionen(starten)));
    expect(ereignisse.map((e) => e.art)).toEqual(["start", "ende", "fehler"]);
  });

  it("Stufe A: --kette uc3 und kein Modell im Start", async () => {
    const { starten } = stromAus([JSON.stringify({ art: "start", kette: ["uc3"] }), zeilen.ende]);
    const umgebung = { KIC_ONLINE: "1", KIC_ONLINE_LESEND: "1", KIC_ONLINE_FRAGEN: "1", UC4_KETTE: "uc3" };
    const antwort = await frageAntwort(stromAnfrage({ frage: "x", modell: "mock" }), optionen(starten, { umgebung }));
    expect((await lies(antwort))[0]).toEqual({ art: "start", kette: ["uc3"], modell: null });
    expect(starten.mock.calls[0]?.[1]).toEqual([...ROUTER_ARGV, "--strom", "--kette", "uc3", "--", "x"]);
  });
});

// Echter Prozess (Review !96): `uv run` startet Python als Kind. Fängt ab: ein Abbruch oder Timeout beendet nur den
// direkten Prozess, der Enkel rechnet als Waise weiter und hält stdout offen.
describe("standardStromStarten mit echtem Prozess", () => {
  const ENKEL = 'sleep 30 & echo "$!"; wait';
  const lebt = (pid: number) => {
    try {
      process.kill(pid, 0);
      return true;
    } catch {
      return false;
    }
  };

  it("abbrechen beendet die ganze Prozessgruppe samt Enkel, ende löst auf", async () => {
    const lauf = standardStromStarten("sh", ["-c", ENKEL], { cwd: ".", timeout: 30_000 });
    const { value } = await lauf.zeilen[Symbol.asyncIterator]().next();
    const enkel = Number(value);
    expect(lebt(enkel)).toBe(true);
    lauf.abbrechen();
    expect(await lauf.ende).toBeNull();
    await vi.waitFor(() => expect(lebt(enkel)).toBe(false), { timeout: 3_000 });
  });

  it("auch der Ergebnis-Weg (standardAusfuehren) beendet beim Timeout den Enkel", async () => {
    const pidDatei = `${process.env.TMPDIR ?? "/tmp"}/uc4-enkel-${process.pid}.pid`;
    await expect(
      standardAusfuehren("sh", ["-c", `sleep 30 & echo "$!" > ${pidDatei}; wait`], {
        cwd: ".",
        timeout: 300,
        maxBuffer: 1024,
      }),
    ).rejects.toThrow("TimeoutError");
    const { readFileSync, rmSync } = await import("node:fs");
    const enkel = Number(readFileSync(pidDatei, "utf8"));
    rmSync(pidDatei);
    await vi.waitFor(() => expect(lebt(enkel)).toBe(false), { timeout: 3_000 });
  });

  it("ein Abbruch des Clients beendet den Ergebnis-Weg sofort samt Enkel (#150)", async () => {
    const pidDatei = `${process.env.TMPDIR ?? "/tmp"}/uc4-abbruch-${process.pid}.pid`;
    const steuerung = new AbortController();
    const lauf = standardAusfuehren("sh", ["-c", `sleep 30 & echo "$!" > ${pidDatei}; wait`], {
      cwd: ".",
      timeout: 30_000,
      maxBuffer: 1024,
      signal: steuerung.signal,
    });
    const { existsSync, readFileSync, rmSync } = await import("node:fs");
    await vi.waitFor(() => expect(existsSync(pidDatei) && readFileSync(pidDatei, "utf8").trim() !== "").toBe(true));
    const enkel = Number(readFileSync(pidDatei, "utf8"));
    rmSync(pidDatei);
    const beginn = Date.now();
    steuerung.abort();
    await expect(lauf).rejects.toThrow("AbortError");
    expect(Date.now() - beginn).toBeLessThan(5_000);
    await vi.waitFor(() => expect(lebt(enkel)).toBe(false), { timeout: 3_000 });
  });

  it("der Timeout beendet die Gruppe ebenfalls", async () => {
    const lauf = standardStromStarten("sh", ["-c", ENKEL], { cwd: ".", timeout: 300 });
    const { value } = await lauf.zeilen[Symbol.asyncIterator]().next();
    expect(await lauf.ende).toBeNull();
    await vi.waitFor(() => expect(lebt(Number(value))).toBe(false), { timeout: 3_000 });
  });
});

describe("?station=uc2: Probierseite /uc2/frage mit eigenem Deckel", () => {
  const OFFEN = { UC4_KETTE: "uc3,uc2,uc1" };
  const KI = JSON.stringify({ antworten: [{ text: "T", belege: [], zahlen: [], uc: "uc2", modell: "m", protokoll_id: null }], fehlend: [] });
  const ABSAGE = JSON.stringify({ antworten: [{ text: "T", belege: [], zahlen: [], uc: "uc2", modell: null, protokoll_id: null }], fehlend: [] });
  const stationAnfrage = (ip = "1.1.1.1", ziel = "http://lokal/api/uc4/frage?station=uc2") =>
    new Request(ziel, { method: "POST", headers: { "content-type": "application/json", "x-forwarded-for": ip }, body: JSON.stringify({ frage: "x" }) });

  it("fragt nur uc2", async () => {
    const ausfuehren = liefert(KI);
    const antwort = await frageAntwort(stationAnfrage(), { ausfuehren, umgebung: OFFEN, wurzel: () => "/r" });
    expect(antwort.status).toBe(200);
    const argv = ausfuehren.mock.calls[0]![1];
    expect(argv.slice(argv.indexOf("--kette"), argv.indexOf("--kette") + 2)).toEqual(["--kette", "uc2"]);
  });

  it("öffnet ohne uc2 in der Kette kein Modell (Online Stufe A)", async () => {
    const ausfuehren = liefert(KI);
    const antwort = await frageAntwort(stationAnfrage(), {
      ausfuehren,
      umgebung: { KIC_ONLINE: "1", KIC_ONLINE_LESEND: "1", KIC_ONLINE_FRAGEN: "1", UC4_KETTE: "uc3" },
      wurzel: () => "/r",
    });
    expect(antwort.status).toBe(403);
    expect(ausfuehren).not.toHaveBeenCalled();
  });

  it("nimmt nur uc2 als Station an", async () => {
    const ausfuehren = liefert(KI);
    const antwort = await frageAntwort(stationAnfrage("1.1.1.1", "http://lokal/api/uc4/frage?station=uc1"), { ausfuehren, umgebung: OFFEN, wurzel: () => "/r" });
    expect(antwort.status).toBe(400);
    expect(ausfuehren).not.toHaveBeenCalled();
  });

  it("Limit je Client: fünf je Minute, /uc4 bleibt davon frei", async () => {
    const handler = erstelleFrageAntwort({ ausfuehren: liefert(KI), umgebung: OFFEN, wurzel: () => "/r" });
    for (let i = 0; i < STATION_PRO_MINUTE; i += 1) expect((await handler(stationAnfrage())).status).toBe(200);
    expect((await handler(stationAnfrage())).status).toBe(429);
    expect((await handler(stationAnfrage("2.2.2.2"))).status).toBe(200);
    const kette = await handler(new Request("http://lokal/api/uc4/frage", { method: "POST", headers: { "x-forwarded-for": "1.1.1.1" }, body: JSON.stringify({ frage: "x" }) }));
    expect(kette.status).toBe(200);
  });

  it("Tagesdeckel: voll ist voll, /uc4 läuft weiter, am nächsten UTC-Tag wieder offen, Absagen zählen nicht", async () => {
    let zeit = Date.UTC(2026, 10, 6, 8);
    const ausfuehren = liefert(KI);
    const handler = erstelleFrageAntwort({ ausfuehren, umgebung: OFFEN, wurzel: () => "/r", stationRatenlimit: offen, ratenlimit: offen, jetzt: () => zeit });
    for (let i = 0; i < STATION_FRAGEN_PRO_TAG; i += 1) expect((await handler(stationAnfrage())).status).toBe(200);
    const voll = await handler(stationAnfrage());
    expect(voll.status).toBe(429);
    expect(((await voll.json()) as { fehler: string }).fehler).toBe(DECKEL_MELDUNG);
    const aufrufe = ausfuehren.mock.calls.length;
    expect(aufrufe).toBe(STATION_FRAGEN_PRO_TAG);
    const kette = await handler(new Request("http://lokal/api/uc4/frage", { method: "POST", body: JSON.stringify({ frage: "x" }) }));
    expect(kette.status).toBe(200);
    zeit = Date.UTC(2026, 10, 7, 0, 0, 1);
    expect((await handler(stationAnfrage())).status).toBe(200);

    const absagen = erstelleFrageAntwort({ ausfuehren: liefert(ABSAGE), umgebung: OFFEN, wurzel: () => "/r", stationRatenlimit: offen });
    for (let i = 0; i < STATION_FRAGEN_PRO_TAG + 3; i += 1) expect((await absagen(stationAnfrage())).status).toBe(200);
  });

  it("ein Lauf zur Zeit, eigener Platz: /uc4 läuft daneben", async () => {
    let frei: (l: { code: number; stdout: string }) => void = () => {};
    const ausfuehren = vi.fn<Ausfuehren>(() => new Promise((aufloesen) => (frei = aufloesen)));
    const handler = erstelleFrageAntwort({ ausfuehren, umgebung: OFFEN, wurzel: () => "/r", stationRatenlimit: offen, ratenlimit: offen });
    const erste = handler(stationAnfrage());
    await vi.waitFor(() => expect(ausfuehren).toHaveBeenCalledTimes(1));
    expect((await handler(stationAnfrage())).status).toBe(429);
    const erster = frei;
    const kette = handler(new Request("http://lokal/api/uc4/frage", { method: "POST", body: JSON.stringify({ frage: "x" }) }));
    await vi.waitFor(() => expect(ausfuehren).toHaveBeenCalledTimes(2));
    frei({ code: 0, stdout: KI });
    erster({ code: 0, stdout: KI });
    expect((await erste).status).toBe(200);
    expect((await kette).status).toBe(200);
  });
});
