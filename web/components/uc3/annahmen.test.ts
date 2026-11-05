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

  it("setzt den Kopfsatz in Einzahl und Mehrzahl", () => {
    expect(annahmenKopf(10)).toBe("10 Annahmen gelten, bis die Fachabteilung antwortet.");
    expect(annahmenKopf(1)).toBe("1 Annahme gilt, bis die Fachabteilung antwortet.");
  });
});
