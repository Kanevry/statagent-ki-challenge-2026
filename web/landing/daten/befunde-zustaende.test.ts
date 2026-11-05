import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Gemocktes postgres.js: die Abfragen in befunde.ts laufen gegen festen Zustand, ohne Datenbank.
const zustand: { anzahl: number; zeilen: unknown[] } = { anzahl: 0, zeilen: [] };

vi.mock("postgres", () => ({
  default: () => {
    const sql = (teile: TemplateStringsArray) =>
      Promise.resolve(teile.join("?").includes("count(*)") ? [{ anzahl: String(zustand.anzahl) }] : zustand.zeilen);
    sql.end = () => Promise.resolve();
    return sql;
  },
}));

const { ladeBefunde } = await import("./befunde");

const urlVorher = process.env.UC3_DATABASE_URL;
beforeEach(() => {
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
    beleg_sql: null,
    anhalten: false,
    lauf: { lieferung: "2025-03" },
    regel: { name: `Regel ${i}` },
  };
}

describe("ladeBefunde mit erreichbarer Datenbank", () => {
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
