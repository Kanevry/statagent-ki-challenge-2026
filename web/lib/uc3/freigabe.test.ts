import { describe, expect, it, vi } from "vitest";
import { UC3_ARGV, type Ausfuehren, type CliLauf } from "./cli";
import {
  entscheidungArgv,
  erstelleFreigabeAntwort,
  isoZeit,
  klartext,
  kurzerGrund,
  vorschlagId,
  waage,
  waageBeleg,
} from "./freigabe";

// Nie die echte CLI: jede Antwort kommt aus einem gefälschten `ausfuehren`.
// Echter Aufbau des Aufrufs aus cli.ts; nur der Standard-Ausführer wirft, damit nie die echte CLI läuft.
vi.mock("./cli", async (importOriginal) => {
  const echt = await importOriginal<typeof import("./cli")>();
  return {
    ...echt,
    standardAusfuehren: async () => {
      throw new Error("echte CLI im Test");
    },
  };
});

function anfrage(body: unknown): Request {
  return new Request("http://localhost/api/uc3/freigabe", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

function fake(lauf: Partial<CliLauf> = {}) {
  return vi.fn<Ausfuehren>(async () => ({ code: 0, stdout: "", stderr: "", ...lauf }));
}

const freigabeJson = JSON.stringify({
  vorschlag_id: 1,
  name: "Anna Beispiel",
  commit_hash: "a81f3c2",
  angewendet: true,
  fehler: null,
  meldung: null,
  freigegeben_am: "2026-11-05 14:06:41.123456+01:00",
  ref: "v2/R6_beschaeftigungskategorie",
  protokoll_id: 1,
});

function handler(ausfuehren: Ausfuehren, umgebung: Record<string, string | undefined> = {}) {
  return erstelleFreigabeAntwort({ ausfuehren, umgebung, wurzel: () => "/repo" });
}

describe("POST /api/uc3/freigabe", () => {
  it("Fehler: Online-Demo könnte freigeben. KIC_ONLINE_LESEND=1 sperrt vor dem Subprozess", async () => {
    const aus = fake({ stdout: freigabeJson });
    const antwort = await handler(aus, { KIC_ONLINE_LESEND: "1" })(
      anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "ja" }),
    );
    expect(antwort.status).toBe(403);
    expect((await antwort.json()).fehler).toBe("In der Online-Demo kann nichts freigegeben werden.");
    expect(aus).not.toHaveBeenCalled();
  });

  it("Fehler: eine Rolle gibt frei. „Team“ wird vor dem Subprozess abgewiesen", async () => {
    const aus = fake({ stdout: freigabeJson });
    for (const name of ["Team", "Team Statistik"]) {
      const antwort = await handler(aus)(anfrage({ id: 1, name, entscheidung: "ja" }));
      expect(antwort.status).toBe(400);
    }
    expect(aus).not.toHaveBeenCalled();
  });

  it("Fehler: Shell-Injektion über die Begründung. Sie ist ein eigenes argv-Element", async () => {
    const aus = fake({ stdout: JSON.stringify({ id: 1, status: "abgelehnt", protokoll_id: 1 }) });
    const begruendung = "Passt nicht; rm -rf / && echo $(whoami)";
    const antwort = await handler(aus)(anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "nein", begruendung }));
    expect(antwort.status).toBe(200);
    const [befehl, argv] = aus.mock.calls[0]!;
    expect(befehl).toBe("uv");
    expect(argv).toEqual([
      ...UC3_ARGV,
      "ablehnen", "1", "--name", "Anna Beispiel", "--begruendung", begruendung, "--json",
    ]);
  });

  it("Fehler: Ablehnung ohne Begründung erreicht die CLI", async () => {
    const aus = fake();
    const antwort = await handler(aus)(anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "nein", begruendung: "  " }));
    expect(antwort.status).toBe(400);
    expect(aus).not.toHaveBeenCalled();
  });

  it("Fehler: stderr mit Pfaden landet beim Client. Exit 1 → 409 mit kurzem Grund ohne Pfad", async () => {
    const stderr =
      "nicht freigegeben: Vorschlag uc3/1 ist bereits freigegeben, angewendet in /Users/x/Projects/repo/uc3\nTraceback (most recent call last):\n  File \"/opt/geheim.py\"";
    const aus = fake({ code: 1, stderr });
    const antwort = await handler(aus)(anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "ja" }));
    expect(antwort.status).toBe(409);
    const text = JSON.stringify(await antwort.json());
    expect(text).toContain("ist bereits freigegeben");
    expect(text).not.toContain("/Users");
    expect(text).not.toContain("Traceback");
    expect(text).not.toContain("geheim");
  });

  it("Fehler: gespeicherte Freigabe, deren Anwenden scheiterte, gilt als abgewiesen. Exit 1 mit JSON → 200", async () => {
    const stdout = JSON.stringify({ ...JSON.parse(freigabeJson), angewendet: false, fehler: "RegelKonflikt" });
    const antwort = await handler(fake({ code: 1, stdout }))(anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "ja" }));
    expect(antwort.status).toBe(200);
    expect(await antwort.json()).toMatchObject({ angewendet: false, commit: "a81f3c2" });
  });

  it("Fehler: Zeit der Freigabe ist die Browser-Uhr. Exit 0 liefert freigegeben_am als ISO", async () => {
    const aus = fake({ stdout: freigabeJson });
    const antwort = await handler(aus)(anfrage({ id: 1, name: "  Anna   Beispiel ", entscheidung: "ja" }));
    expect(antwort.status).toBe(200);
    expect(await antwort.json()).toEqual({
      zeitpunkt: "2026-11-05T14:06:41.123+01:00",
      commit: "a81f3c2",
      protokoll_id: 1,
      angewendet: true,
    });
    expect(aus.mock.calls[0]![1]).toEqual([...UC3_ARGV, "freigabe", "1", "--name", "Anna Beispiel", "--json"]);
  });

  it("Fehler: Timeout bringt den Server zum Absturz. Startfehler → 502", async () => {
    const aus = vi.fn<Ausfuehren>(async () => {
      throw Object.assign(new Error("spawn uv ENOENT /Users/x"), { name: "Error" });
    });
    const antwort = await handler(aus)(anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "ja" }));
    expect(antwort.status).toBe(502);
    expect(JSON.stringify(await antwort.json())).not.toContain("/Users");
  });

  it("Fehler: Body ohne Grenze. Über 4 KiB → 413, ungültige ID → 400", async () => {
    const aus = fake();
    const gross = await handler(aus)(anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "ja", x: "a".repeat(5000) }));
    expect(gross.status).toBe(413);
    for (const id of [0, -1, 1.5, "1"]) {
      expect((await handler(aus)(anfrage({ id, name: "Anna Beispiel", entscheidung: "ja" }))).status).toBe(400);
    }
    expect(aus).not.toHaveBeenCalled();
  });

  it("Fehler: zwei Freigaben gleichzeitig schreiben denselben Commit. Die zweite → 429", async () => {
    let loesen: (l: CliLauf) => void = () => {};
    const aus = vi.fn<Ausfuehren>(() => new Promise((r) => (loesen = r)));
    const h = handler(aus);
    const erste = h(anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "ja" }));
    await vi.waitFor(() => expect(aus).toHaveBeenCalledTimes(1));
    const zweite = await h(anfrage({ id: 2, name: "Anna Beispiel", entscheidung: "ja" }));
    expect(zweite.status).toBe(429);
    loesen({ code: 0, stdout: freigabeJson, stderr: "" });
    expect((await erste).status).toBe(200);
  });
});

describe("Freigabe-Waage", () => {
  const probe = {
    "2025-10": {
      lieferung: "2025-10",
      vorher: {
        regelsatz: "v1",
        gesamt: 410587,
        zellen: 100,
        je_merkmal: {
          qualifikation: { ArbeiterDV: 200000, ArbeiterFD: 10000, AngestellteDV: 190000, AngestellteFD: 10587 },
          geschlecht: { M: 210000, W: 200587 },
        },
      },
      nachher: {
        regelsatz: "v2",
        gesamt: 410587,
        zellen: 80,
        je_merkmal: { qualifikation: { Arbeiter: 210000, Angestellte: 200587 }, geschlecht: { M: 210000, W: 200587 } },
      },
      differenz_gesamt: 0,
    },
  };

  it("Fehler: Waage zeigt die gleichbleibende Gesamtzahl. Sie zeigt die geänderte Kategorie", () => {
    const w = waage(probe, { qualifikation: { Arbeiter: "Arbeiter" } });
    expect(w).not.toBeNull();
    expect(w!.haupt).toMatchObject({ code: "Arbeiter", vorher: 0, nachher: 210000, bezeichnung: "Arbeiter (Qualifikation)" });
    expect(w!.haupt.merkmal).not.toBe("gesamt");
    // Unveränderte Kategorien (Geschlecht) stehen auch nicht unter „weitere“.
    expect(w!.weitere.map((z) => z.merkmal)).not.toContain("geschlecht");
    expect(w!.weitere).toHaveLength(5);
  });

  it("Fehler: leere Probe erfindet Zahlen. Ohne Probe → null", () => {
    expect(waage({})).toBeNull();
    expect(waage({ "2025-10": { lieferung: "2025-10", hinweis: "Code-Datei ändert keine Zahl" } })).toBeNull();
  });

  it("Fehler: Beleg zeigt eine andere Zahl als die Waage. SQL zielt auf genau Merkmal und Code", () => {
    const w = waage(probe)!;
    const sql = waageBeleg(1, w).sql ?? "";
    expect(sql).toContain("probe->'2025-10'->'nachher'->'je_merkmal'->'qualifikation'->>'Arbeiter'");
    expect(sql).toContain("->'vorher'->");
    expect(sql).toContain("WHERE id = 1;");
  });
});

describe("Hilfen", () => {
  it("Fehler: Regeländerung ohne Wortlaut. Klartext mit - und + nur für geänderte Werte", () => {
    const { worte, diff } = klartext({
      typ: "regel_aendern",
      aenderungen: [
        {
          regel_name: "R6",
          parameter_alt: { qualifikation: "code", gleich: 1 },
          parameter_neu: { qualifikation: "beschaeftigungskategorie", gleich: 1 },
        },
      ],
    });
    expect(worte).toEqual(["In der Regel R6 wird „qualifikation“ von „code“ auf „beschaeftigungskategorie“ geändert."]);
    expect(diff).toBe("- R6: qualifikation = „code“\n+ R6: qualifikation = „beschaeftigungskategorie“");
  });

  it("Fehler: Routen-ID „1abc“ oder „0“ öffnet einen Vorschlag", () => {
    expect(vorschlagId("1")).toBe(1);
    for (const t of ["0", "1abc", "-1", "01", "99999999999"]) expect(vorschlagId(t)).toBeNull();
  });

  it("Fehler: Python-Zeit ohne T zeigt im Browser „Invalid Date“", () => {
    expect(isoZeit("2026-11-05 14:41:07.655871+01:00")).toBe("2026-11-05T14:41:07.655+01:00");
    expect(isoZeit("2026-11-05 14:41:07+01")).toBe("2026-11-05T14:41:07+01:00");
    expect(isoZeit("None")).toBeNull();
  });

  it("Fehler: ohne erkennbaren Grund wird stderr durchgereicht", () => {
    expect(kurzerGrund("Traceback /opt/x.py")).toBeNull();
    expect(kurzerGrund("nicht abgelehnt: Eine Ablehnung braucht eine Begründung")).toBe(
      "Eine Ablehnung braucht eine Begründung",
    );
    expect(entscheidungArgv({ id: 3, name: "Anna Beispiel", entscheidung: "ja" })).toEqual([
      "freigabe", "3", "--name", "Anna Beispiel", "--json",
    ]);
  });
});
