import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { annahmenKopf, geltungSatz, HERLEITUNG } from "./annahmen";

describe("Annahmen als Bereich", () => {
  // Fehler, den das fängt: Die Seite nennt eine Annahme, die es im Dokument nicht (mehr) gibt.
  it("hält A1 bis A13 mit dem Dokument gleich", () => {
    const dokument = readFileSync(resolve(__dirname, "../../../docs/plan/uc3/annahmen.md"), "utf8");
    expect(HERLEITUNG.map((a) => a.nr)).toEqual(Array.from({ length: 13 }, (_, i) => `A${i + 1}`));
    for (const { nr } of HERLEITUNG) expect(dokument).toMatch(new RegExp(`^\\| ${nr} \\|`, "m"));
    for (const { nr, name } of HERLEITUNG.slice(0, 10)) {
      const zeile = dokument.split("\n").find((z) => z.startsWith(`| ${nr} |`))!;
      // Anführungszeichen schreibt die Seite typografisch, das Dokument gerade.
      const gerade = (t: string) => t.replace(/[„“"]/g, "");
      expect(gerade(zeile)).toContain(gerade(name));
    }
  });

  it("nennt die Geltung in Worten, ohne JJJJ-MM", () => {
    expect(geltungSatz(null)).toBe("gilt für alle Monate");
    expect(geltungSatz(["2025-10"])).toBe("gilt für Oktober 2025");
    expect(geltungSatz(["2025-05", "2026-02"])).toBe("gilt für Mai 2025 und Februar 2026");
  });

  // Fehler, den das fängt: „10 Annahmen gelten, bis die Fachabteilung antwortet“, obwohl zwei keine Rückfrage haben
  // (Review 9b, F5 und F10).
  it("sagt nur für Annahmen mit offener Rückfrage, dass sie warten", () => {
    expect(annahmenKopf(10, 8)).toBe("Wir rechnen mit 10 Annahmen. 8 warten auf die Fachabteilung.");
    expect(annahmenKopf(10, 1)).toBe("Wir rechnen mit 10 Annahmen. 1 wartet auf die Fachabteilung.");
    expect(annahmenKopf(10, 0)).toBe("Wir rechnen mit 10 Annahmen.");
    expect(annahmenKopf(1, 1)).toBe("Wir rechnen mit 1 Annahme. 1 wartet auf die Fachabteilung.");
  });
});
