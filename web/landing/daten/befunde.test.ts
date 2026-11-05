import { afterEach, describe, expect, it, vi } from "vitest";
import { ladeBefunde, zeileAusTreffer } from "./befunde";

const urlVorher = process.env.UC3_DATABASE_URL;
afterEach(() => {
  process.env.UC3_DATABASE_URL = urlVorher;
  vi.restoreAllMocks();
});

describe("ladeBefunde", () => {
  it("zeigt ohne Datenbank die 8 Befunde der Gegenrechnung als Beispieldaten (Oracle #58)", async () => {
    delete process.env.UC3_DATABASE_URL;
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const t = await ladeBefunde();
    expect(t.quelle).toBe("beispieldaten");
    expect(t.zeilen).toHaveLength(8);
    const alles = t.zeilen.map((z) => `${z.befund} ${z.saetze}`).join(" | ");
    for (const zahl of ["1.663", "1.492", "78.949", "−260"]) expect(alles).toContain(zahl);
  });

  it("fällt bei unerreichbarer Datenbank schnell zurück und nennt das Passwort nicht", async () => {
    process.env.UC3_DATABASE_URL = "postgres://nutzer:geheimeswort@127.0.0.1:1/nichts";
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const start = Date.now();
    const t = await ladeBefunde();
    expect(Date.now() - start).toBeLessThan(3_500);
    expect(t.quelle).toBe("beispieldaten");
    expect(t.grund).toBe("keine-verbindung");
    expect(JSON.stringify(warn.mock.calls)).not.toContain("geheimeswort");
  });

});

describe("zeileAusTreffer", () => {
  it("liest Lieferung und Regelnamen aus den JSON-Zeilen und markiert fehlende Einstufung als offen", () => {
    const z = zeileAusTreffer({
      anzahl: "78949",
      umfang: null,
      einstufung: null,
      beleg_sql: "\nselect count(*) from roh.lieferung",
      anhalten: true,
      lauf: { id: 7, lieferung: "2025-10" },
      regel: { id: 3, name: "Bestandsrückgang über 5 %" },
    });
    expect(z).toMatchObject({
      befund: "Bestandsrückgang über 5 %",
      lieferung: "2025-10",
      saetze: "78.949",
      einstufungText: "offen · Lauf angehalten",
      beleg: "select count(*) from roh.lieferung",
    });
  });
});
