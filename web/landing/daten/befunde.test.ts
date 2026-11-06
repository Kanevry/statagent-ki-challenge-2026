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
  const roh = {
    anzahl: "78949",
    umfang: "Vormonat 78.949" as string | null,
    einstufung: "erklaert-datenproblem" as string | null,
    anhalten: true,
    lieferung: "2025-10",
    name: "P16_verhaeltnisse_verschwunden" as string | null,
    beschreibung: "Roher Text der Regel." as string | null,
    satz: null as string | null,
  };

  it("zeigt Klartext statt Rohname und keinen SQL-Beleg", () => {
    const z = zeileAusTreffer(roh);
    expect(z.befund).toBe("Beschäftigungsverhältnisse des Vormonats fehlen in der Lieferung.");
    expect(z.befund).not.toContain("P16");
    expect(z.beleg).toBeUndefined();
    expect(z).toMatchObject({ lieferung: "2025-10", saetze: "78.949", anhalten: true, einstufungText: "erklärt, Datenproblem · hält den Monat an" });
  });

  it("nimmt die Satzvorlage der Regel und schreibt den Monat aus", () => {
    const z = zeileAusTreffer({ ...roh, satz: "Im {monat} fehlen {anzahl} Zeilen.", anhalten: false });
    expect(z.befund).toBe("Im Oktober 2025 fehlen 78.949 Zeilen.");
    expect(z.einstufungText).toBe("erklärt, Datenproblem");
  });

  it("zeigt nur den ersten Satz, Folgesätze meinen die Monatsseite", () => {
    const z = zeileAusTreffer({ ...roh, satz: "Frühere Monate sehen anders aus. Das steht unten als Revisionsbedarf." });
    expect(z.befund).toBe("Frühere Monate sehen anders aus.");
  });

  it("markiert eine fehlende Einstufung als nicht eingestuft", () => {
    const z = zeileAusTreffer({ ...roh, einstufung: null, anhalten: false });
    expect(z.einstufung).toBe("nicht-erklaerbar");
    expect(z.einstufungText).toBe("nicht eingestuft");
  });
});
