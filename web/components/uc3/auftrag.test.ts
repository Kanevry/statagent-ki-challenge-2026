import { describe, expect, it, vi } from "vitest";
import { UC3_ARGV, type Ausfuehren, type CliLauf } from "./cli";
import {
  auftragArgv,
  erstelleAuftragWeg,
  ergebnisAus,
  leseEingabe,
  rechenbareMonate,
  MAX_BODY_BYTES,
  vorfuehrungOffen,
  type AuftragStand,
} from "./auftrag";

const OFFEN = { KIC_VORFUEHRUNG: "1" };

function post(body: unknown): Request {
  return new Request("http://x/api/uc3/auftrag", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

async function stand(antwort: Response): Promise<AuftragStand | null> {
  return ((await antwort.json()) as { stand: AuftragStand | null }).stand;
}

describe("vorfuehrungOffen", () => {
  it("nur mit dem Schalter, und die lesende Online-Demo gewinnt immer", () => {
    expect(vorfuehrungOffen({})).toBe(false);
    expect(vorfuehrungOffen(OFFEN)).toBe(true);
    expect(vorfuehrungOffen({ KIC_VORFUEHRUNG: "1", KIC_ONLINE_LESEND: "1" })).toBe(false);
  });
});

describe("Eingabe und Aufruf", () => {
  it("ein Satz mit führendem Strich bleibt ein Satz, keine Option", () => {
    expect(auftragArgv({ art: "agent", anweisung: "--ohne-probe" })).toEqual(["agent", "--json", "--", "--ohne-probe"]);
  });

  it("weist leere Sätze, falsche Monate und unbekannte Arten ab", () => {
    expect(leseEingabe('{"art":"agent","anweisung":"  "}')).toHaveProperty("meldung");
    expect(leseEingabe('{"art":"lauf","lieferung":"2025-13","regelsatz":"v2"}')).toHaveProperty("meldung");
    expect(leseEingabe('{"art":"lauf","lieferung":"2025-10; rm","regelsatz":"v2"}')).toHaveProperty("meldung");
    expect(leseEingabe('{"art":"lauf","lieferung":"2025-10","regelsatz":"--alle"}')).toHaveProperty("meldung");
    expect(leseEingabe('{"art":"sql"}')).toHaveProperty("meldung");
    expect(leseEingabe("kein json")).toHaveProperty("meldung");
  });
});

describe("Probemonat", () => {
  it("geht als Option vor dem Satz mit, ohne Angabe entscheidet die CLI", () => {
    expect(auftragArgv({ art: "agent", anweisung: "x", probe: "2025-03" })).toEqual(["agent", "--json", "--probe", "2025-03", "--", "x"]);
    expect(leseEingabe('{"art":"agent","anweisung":"x","probe":""}')).toEqual({ art: "agent", anweisung: "x" });
    expect(leseEingabe('{"art":"agent","anweisung":"x","probe":"--ohne-probe"}')).toHaveProperty("meldung");
  });
});

describe("rechenbareMonate", () => {
  const alle = ["2024-08", "2024-09", "2024-10"];

  it("ein neuer Regelsatz beginnt beim ersten Monat, sonst scheitert der Lauf an der Reihenfolge", () => {
    expect(rechenbareMonate(alle, new Set())).toEqual(["2024-08"]);
    expect(rechenbareMonate(alle, new Set(["2024-08"]))).toEqual(["2024-09", "2024-08"]);
  });

  it("alle gerechnet: alle wählbar, neueste zuerst", () => {
    expect(rechenbareMonate(alle, new Set(alle))).toEqual(["2024-10", "2024-09", "2024-08"]);
  });
});

describe("ergebnisAus", () => {
  it("unterscheidet Vorschlag, Rückfrage, Ablehnung und Fehler", () => {
    expect(ergebnisAus("agent", 0, '{"vorschlag_id":7,"wirkung":"R5 auf 15"}', "")).toMatchObject({
      zustand: "vorschlag",
      vorschlagId: 7,
      satz: "R5 auf 15",
    });
    expect(ergebnisAus("agent", 0, '{"rueckfrage":"Welcher Monat?"}', "").zustand).toBe("rueckfrage");
    expect(ergebnisAus("agent", 1, '{"abgelehnt":"Keine Regel passt."}', "").zustand).toBe("abgelehnt");
    expect(ergebnisAus("agent", 1, "", "Modell nicht erreichbar, kein Vorschlag\n")).toMatchObject({
      zustand: "fehler",
      satz: "Modell nicht erreichbar, kein Vorschlag",
    });
  });

  it("liest Zahl und Hash eines Laufs", () => {
    expect(ergebnisAus("lauf", 0, '{"gezaehlt":390900,"ergebnis_hash":"abc"}', "")).toMatchObject({
      zustand: "gerechnet",
      gezaehlt: 390900,
      ergebnisHash: "abc",
    });
    expect(ergebnisAus("lauf", 1, "", "2025-10: abgebrochen\n")).toMatchObject({ zustand: "fehler" });
  });
});

describe("erstelleAuftragWeg", () => {
  it("antwortet sofort, während der Lauf weiterrechnet, und meldet danach das Ergebnis", async () => {
    let fertig!: (lauf: CliLauf) => void;
    const ausfuehren = vi.fn<Ausfuehren>(() => new Promise((aufloesen) => (fertig = aufloesen)));
    const weg = erstelleAuftragWeg({ umgebung: OFFEN, ausfuehren });

    const start = await weg.starte(post({ art: "agent", anweisung: "Altersgrenze auf 15" }));
    expect(start.status).toBe(202);
    expect((await stand(start))?.zustand).toBe("laeuft");
    expect(ausfuehren.mock.calls[0]?.[1]).toEqual([...UC3_ARGV, "agent", "--json", "--", "Altersgrenze auf 15"]);

    // ein zweiter Auftrag startet keinen zweiten Lauf
    const zweiter = await weg.starte(post({ art: "lauf", lieferung: "2025-10", regelsatz: "v2" }));
    expect(zweiter.status).toBe(409);
    expect(ausfuehren).toHaveBeenCalledTimes(1);
    expect((await stand(weg.stand()))?.zustand).toBe("laeuft");

    fertig({ code: 0, stdout: '{"vorschlag_id":3,"wirkung":"Alter 15"}', stderr: "" });
    await vi.waitFor(async () => expect((await stand(weg.stand()))?.zustand).toBe("vorschlag"));
    expect((await stand(weg.stand()))?.vorschlagId).toBe(3);
  });

  it("ein Timeout des Programms wird ein Fehler-Stand, kein hängender Lauf", async () => {
    const weg = erstelleAuftragWeg({ umgebung: OFFEN, ausfuehren: () => Promise.reject(new Error("killed")) });
    await weg.starte(post({ art: "lauf", lieferung: "2025-10", regelsatz: "v2" }));
    await vi.waitFor(async () => expect((await stand(weg.stand()))?.zustand).toBe("fehler"));
  });

  it("öffentliche Demo: 403 auf beiden Wegen, nichts startet", async () => {
    const ausfuehren = vi.fn<Ausfuehren>();
    for (const umgebung of [{}, { KIC_VORFUEHRUNG: "1", KIC_ONLINE_LESEND: "1" }]) {
      const weg = erstelleAuftragWeg({ umgebung, ausfuehren });
      expect((await weg.starte(post({ art: "agent", anweisung: "x" }))).status).toBe(403);
      expect(weg.stand().status).toBe(403);
    }
    expect(ausfuehren).not.toHaveBeenCalled();
  });

  it("zu großer Body 413, ungültig 400, ohne Lauf", async () => {
    const ausfuehren = vi.fn<Ausfuehren>();
    const weg = erstelleAuftragWeg({ umgebung: OFFEN, ausfuehren });
    expect((await weg.starte(post("x".repeat(MAX_BODY_BYTES + 1)))).status).toBe(413);
    expect((await weg.starte(post({ art: "agent", anweisung: "" }))).status).toBe(400);
    expect(ausfuehren).not.toHaveBeenCalled();
  });
});
