import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Gemocktes postgres.js: die Abfragen in befunde.ts laufen gegen festen Zustand, ohne Datenbank.
const zustand: { anzahl: number; zeilen: unknown[]; abfragen: { text: string; parameter: unknown[] }[] } = {
  anzahl: 0,
  zeilen: [],
  abfragen: [],
};

vi.mock("postgres", () => ({
  default: () => ({
    unsafe: (text: string, parameter: unknown[] = []) => {
      zustand.abfragen.push({ text, parameter });
      return Promise.resolve(text.includes("count(*)") ? [{ anzahl: String(zustand.anzahl) }] : zustand.zeilen);
    },
    end: () => Promise.resolve(),
  }),
}));

const { befundeZwischenspeicherLeeren, ladeBefunde, ZWISCHENSPEICHER_MS } = await import("./befunde");

const urlVorher = process.env.UC3_DATABASE_URL;
beforeEach(() => {
  befundeZwischenspeicherLeeren();
  zustand.abfragen = [];
  process.env.UC3_DATABASE_URL = "postgres://nutzer:pw@db.invalid:5433/statistik";
  vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => {
  process.env.UC3_DATABASE_URL = urlVorher;
  vi.restoreAllMocks();
});

function treffer(i: number) {
  return {
    anzahl: String(1000 - i),
    umfang: null,
    einstufung: "erklaert-datenproblem",
    anhalten: false,
    lieferung: "2025-03",
    name: `Regel ${i}`,
    beschreibung: `Regel ${i}.`,
    satz: null,
  };
}

describe("ladeBefunde mit erreichbarer Datenbank", () => {
  it("Zeilen und Gesamtzahl lesen nur den maßgeblichen Lauf je Monat in Regelsatz v1", async () => {
    zustand.anzahl = 1;
    zustand.zeilen = [treffer(0)];
    await ladeBefunde();
    expect(zustand.abfragen).toHaveLength(2);
    for (const { text, parameter } of zustand.abfragen) {
      expect(parameter).toEqual(["v1"]);
      expect(text).toContain("WHERE regelsatz = $1 AND status IN ('fertig', 'unveraendert')");
      expect(text).toContain("t.lauf_id = m.quelle_id AND t.anzahl > 0");
    }
  });

  it("leere Treffertabelle: Gegenrechnung mit Grund keine-treffer, nicht keine-verbindung", async () => {
    zustand.anzahl = 0;
    zustand.zeilen = [];
    const t = await ladeBefunde();
    expect(t.quelle).toBe("beispieldaten");
    expect(t.grund).toBe("keine-treffer");
  });

  it("mehr Treffer als angezeigt: 50 Zeilen, Gesamtzahl bleibt erhalten (Hinweis N von M)", async () => {
    zustand.anzahl = 120;
    zustand.zeilen = Array.from({ length: 50 }, (_, i) => treffer(i));
    const t = await ladeBefunde();
    expect(t.quelle).toBe("datenbank");
    expect(t.zeilen).toHaveLength(50);
    expect(t.anzahl).toBe(120);
  });
});

// Landing rendert je Anfrage (force-dynamic): Fängt ab, dass jede Anfrage eine eigene Verbindung öffnet, dass ein
// Ausfall der Datenbank 60 s lang Beispieldaten festschreibt, oder dass ein alter Stand nie abläuft.
describe("ladeBefunde merkt sich einen Stand aus der Datenbank 60 s", () => {
  it("liefert innerhalb von 60 s den gemerkten Stand, danach frisch; Beispieldaten merkt es nicht", async () => {
    zustand.anzahl = 0;
    zustand.zeilen = [];
    expect((await ladeBefunde(0)).quelle).toBe("beispieldaten");
    zustand.anzahl = 2;
    zustand.zeilen = [treffer(1), treffer(2)];
    expect((await ladeBefunde(1)).anzahl).toBe(2);
    zustand.anzahl = 3;
    zustand.zeilen = [treffer(1), treffer(2), treffer(3)];
    expect((await ladeBefunde(ZWISCHENSPEICHER_MS)).anzahl).toBe(2);
    expect((await ladeBefunde(ZWISCHENSPEICHER_MS + 2)).anzahl).toBe(3);
  });

  it("meldet eine leere Treffertabelle im Log", async () => {
    zustand.anzahl = 0;
    zustand.zeilen = [];
    await ladeBefunde();
    expect(JSON.stringify(vi.mocked(console.warn).mock.calls)).toContain("meta.pruefung_treffer ist leer");
  });
});
