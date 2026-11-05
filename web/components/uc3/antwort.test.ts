import { describe, expect, it, vi } from "vitest";
import { alsCsv, erstelleFrageAntwort, frageFehlt, istRueckfrage, zerlegeAntwort } from "./antwort";
import { UC3_ARGV, uc3, type Ausfuehren, type CliLauf } from "./cli";
import bundeslaender from "./fixtures/antwort-bundeslaender-2025-10.json";
import ohneMonat from "./fixtures/antwort-ohne-monat.json";
import wien from "./fixtures/antwort-wien-2025-03.json";

// Nie die echte CLI: jede Antwort kommt aus einem gefälschten `ausfuehren`. Die Fixtures sind echte Ausgaben von
// `uc3 antwort --json` (05.11.).
vi.mock("./cli", async (importOriginal) => {
  const echt = await importOriginal<typeof import("./cli")>();
  return {
    ...echt,
    standardAusfuehren: async () => {
      throw new Error("echte CLI im Test");
    },
  };
});

const NOCH_NICHT: CliLauf = { code: 2, stdout: "", stderr: "frage: noch nicht umgesetzt (#74).\n" };
const OHNE_JSON_SCHALTER: CliLauf = {
  code: 2,
  stdout: "",
  stderr: "Usage: uc3 frage [OPTIONS] {text}\n╭─ Error ─╮\n│ No such option: --json │\n╰─╯\n",
};
const ok = (daten: unknown): CliLauf => ({ code: 0, stdout: JSON.stringify(daten), stderr: "" });

function anfrage(body: unknown): Request {
  return new Request("http://localhost/api/uc3/frage", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

/** Fake mit einer Antwort je Aufruf, in Reihenfolge. */
function folge(...laeufe: CliLauf[]) {
  const liste = [...laeufe];
  return vi.fn<Ausfuehren>(async () => liste.shift() ?? { code: 99, stdout: "", stderr: "" });
}

function handler(ausfuehren: Ausfuehren, umgebung: Record<string, string | undefined> = {}, maxLaeufe?: number) {
  return erstelleFrageAntwort({ starte: uc3, ausfuehren, umgebung, wurzel: () => "/repo", ...(maxLaeufe ? { maxLaeufe } : {}) });
}

describe("POST /api/uc3/frage", () => {
  it("Fehler: Online-Demo startet Python. KIC_ONLINE_LESEND=1 sperrt vor jedem Subprozess", async () => {
    const aus = folge(ok(wien));
    const antwort = await handler(aus, { KIC_ONLINE_LESEND: "1" })(anfrage({ frage: "Beschäftigte 2025" }));
    expect(antwort.status).toBe(403);
    expect(await antwort.json()).toEqual({ fehler: "Fragen an die Daten sind in der Online-Demo gesperrt." });
    expect(aus).not.toHaveBeenCalled();
  });

  // Fehler: Mit KIC_ONLINE_FRAGEN=1 (E0, Stufe A) blieben Fragen online trotzdem gesperrt.
  it("KIC_ONLINE_FRAGEN=1 gibt Fragen in der lesenden Online-Demo frei", async () => {
    const aus = folge(ok(wien));
    const antwort = await handler(aus, { KIC_ONLINE_LESEND: "1", KIC_ONLINE_FRAGEN: "1" })(anfrage({ frage: "Beschäftigte in Wien im März 2025" }));
    expect(antwort.status).toBe(200);
    expect(aus).toHaveBeenCalledTimes(1);
  });

  it("Fehler: Frage „-h“ wird ein Schalter. `--` steht direkt vor der Frage, nach --json", async () => {
    const aus = folge(ok(ohneMonat));
    await handler(aus)(anfrage({ frage: "-h" }));
    expect(aus).toHaveBeenCalledTimes(1);
    const [befehl, argv, optionen] = aus.mock.calls[0]!;
    expect(befehl).toBe("uv");
    expect(argv).toEqual([...UC3_ARGV, "frage", "--json", "--", "-h"]);
    expect(optionen).toMatchObject({ cwd: "/repo", timeout: 60_000 });
  });

  it("Fehler: Rückfall fehlt, solange #74 offen ist. Exit 2 + „noch nicht umgesetzt“ ruft antwort", async () => {
    const aus = folge(NOCH_NICHT, ok(wien));
    const antwort = await handler(aus)(anfrage({ frage: "Beschäftigte in Wien im März 2025" }));
    expect(antwort.status).toBe(200);
    const daten = await antwort.json();
    expect(daten.quelle).toBe("antwort");
    expect(daten.antwort.zahlen[0].wert).toBe(91450);
    expect(aus.mock.calls[1]![1]).toEqual([...UC3_ARGV, "antwort", "--json", "--", "Beschäftigte in Wien im März 2025"]);
  });

  it("Fehler: heutiger Platzhalter kennt --json nicht (typer, Exit 2). Auch das ist „noch nicht da“", async () => {
    const aus = folge(OHNE_JSON_SCHALTER, ok(wien));
    const antwort = await handler(aus)(anfrage({ frage: "Beschäftigte in Wien im März 2025" }));
    expect(antwort.status).toBe(200);
    expect((await antwort.json()).quelle).toBe("antwort");
  });

  it("Fehler: jeder Exit 2 fällt auf antwort zurück. Anderer Exit-2-Fehler → 502 ohne zweiten Lauf", async () => {
    const aus = folge({ code: 2, stdout: "", stderr: "Error: Missing argument 'TEXT'." }, ok(wien));
    const antwort = await handler(aus)(anfrage({ frage: "Beschäftigte in Wien im März 2025" }));
    expect(antwort.status).toBe(502);
    expect(aus).toHaveBeenCalledTimes(1);
    expect(frageFehlt({ code: 1, stdout: "", stderr: "noch nicht umgesetzt" })).toBe(false);
  });

  it("Fehler: fertiges frage wird übergangen. Exit 0 von frage liefert quelle frage mit definition", async () => {
    const aus = folge(ok({ ...wien, definition: "Gezählt werden Verhältnisse, nicht Personen.", rueckfrage: null }));
    const daten = await (await handler(aus)(anfrage({ frage: "Wien März 2025" }))).json();
    expect(aus).toHaveBeenCalledTimes(1);
    expect(daten).toMatchObject({ quelle: "frage", definition: "Gezählt werden Verhältnisse, nicht Personen.", rueckfrage: null });
  });

  it("Fehler: Zahl ohne Beleg wird gezeigt. zahlen[].beleg außerhalb von belege → 502", async () => {
    const kaputt = { ...wien, zahlen: [{ ...wien.zahlen[0], beleg: 1 }] };
    const antwort = await handler(folge(ok(kaputt)))(anfrage({ frage: "Wien März 2025" }));
    expect(antwort.status).toBe(502);
    expect(JSON.stringify(await antwort.json())).not.toMatch(/beleg=|Traceback/);
  });

  it("Fehler: leere oder zu lange Frage startet Python. 400 ohne Subprozess, Body > 4 KiB → 413", async () => {
    const aus = folge();
    expect((await handler(aus)(anfrage({ frage: "   " }))).status).toBe(400);
    expect((await handler(aus)(anfrage({ frage: "x".repeat(501) }))).status).toBe(400);
    expect((await handler(aus)(anfrage({ frage: 5 }))).status).toBe(400);
    expect((await handler(aus)(anfrage("{kein json"))).status).toBe(400);
    expect((await handler(aus)(anfrage({ frage: "x".repeat(5000) }))).status).toBe(413);
    expect(aus).not.toHaveBeenCalled();
  });

  it("Fehler: Timeout oder Startfehler wird 500 mit Stack. Werfen → 502 mit festem Satz, nichts geloggt außer Art", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const aus = vi.fn<Ausfuehren>(async () => {
      throw Object.assign(new Error("geheime Frage /Users/x"), { name: "TimeoutError" });
    });
    const antwort = await handler(aus)(anfrage({ frage: "geheime Frage" }));
    expect(antwort.status).toBe(502);
    expect(warn.mock.calls.flat().join(" ")).not.toContain("geheime");
    warn.mockRestore();
  });

  it("Fehler: Läufe stauen sich. Der dritte gleichzeitige Lauf bekommt 429, der Slot wird danach frei", async () => {
    let loesen: () => void = () => {};
    const warten = new Promise<void>((r) => (loesen = r));
    const aus = vi.fn<Ausfuehren>(async () => {
      await warten;
      return ok(wien);
    });
    const h = handler(aus, {}, 2);
    const a = h(anfrage({ frage: "a" }));
    const b = h(anfrage({ frage: "b" }));
    expect((await h(anfrage({ frage: "c" }))).status).toBe(429);
    loesen();
    expect((await a).status).toBe(200);
    expect((await b).status).toBe(200);
    expect((await h(anfrage({ frage: "d" }))).status).toBe(200);
  });
});

describe("zerlegeAntwort", () => {
  it("Fehler: definition/rueckfrage sprengen das strikte Schema. Sie werden vorher abgetrennt", () => {
    const z = zerlegeAntwort({ ...ohneMonat, definition: "Satz.", rueckfrage: "Welcher Monat?" });
    expect(z).toMatchObject({ ok: true, definition: "Satz.", rueckfrage: "Welcher Monat?" });
    if (z.ok) expect(istRueckfrage(z.antwort, z.rueckfrage)).toBe(true);
  });

  it("Fehler: fremde Felder rutschen durch. Ein unbekanntes Feld oder definition als Zahl ist ungültig", () => {
    expect(zerlegeAntwort({ ...wien, extra: 1 }).ok).toBe(false);
    expect(zerlegeAntwort({ ...wien, definition: 3 }).ok).toBe(false);
    expect(zerlegeAntwort(null).ok).toBe(false);
  });

  it("Fehler: echte CLI-Ausgaben passen nicht. Alle drei Fixtures sind gültig; ohne Monat ist eine Rückfrage", () => {
    for (const f of [wien, bundeslaender, ohneMonat]) expect(zerlegeAntwort(f).ok).toBe(true);
    const z = zerlegeAntwort(ohneMonat);
    if (z.ok) expect(istRueckfrage(z.antwort, z.rueckfrage)).toBe(true);
    const w = zerlegeAntwort(wien);
    if (w.ok) expect(istRueckfrage(w.antwort, w.rueckfrage)).toBe(false);
  });
});

describe("alsCsv", () => {
  it("Fehler: Semikolon oder Anführungszeichen in der Bezeichnung verschiebt Spalten. Feld wird gequotet", () => {
    const z = zerlegeAntwort(wien);
    if (!z.ok) throw new Error("Fixture ungültig");
    const antwort = { ...z.antwort, zahlen: [{ ...z.antwort.zahlen[0]!, bezeichnung: 'Wien; "Stadt"' }] };
    const [kopf, zeile] = alsCsv(antwort).split("\r\n");
    expect(kopf).toBe("bezeichnung;wert;einheit;lieferung;sql");
    expect(zeile!.startsWith('"Wien; ""Stadt""";91450;Anzahl;2025-03;')).toBe(true);
  });

  it("Fehler: Bezeichnung wird in Excel eine Formel. Führendes = bekommt einen Apostroph", () => {
    const z = zerlegeAntwort(wien);
    if (!z.ok) throw new Error("Fixture ungültig");
    const antwort = { ...z.antwort, zahlen: [{ ...z.antwort.zahlen[0]!, bezeichnung: "=HYPERLINK(1)" }] };
    expect(alsCsv(antwort).split("\r\n")[1]!.startsWith("'=HYPERLINK(1);")).toBe(true);
  });

  it("Fehler: eine Zeile je Zahl fehlt. Zehn Bundesländer ergeben elf Zeilen mit SQL", () => {
    const z = zerlegeAntwort(bundeslaender);
    if (!z.ok) throw new Error("Fixture ungültig");
    const zeilen = alsCsv(z.antwort).trimEnd().split("\r\n");
    expect(zeilen).toHaveLength(11);
    expect(zeilen[10]).toContain("GROUP BY 1 ORDER BY 1");
  });
});
