// @vitest-environment node
import { describe, expect, it } from "vitest";
import pflege from "./fixtures/pflege.json";
import { belegeHash, pruefeReplay } from "./replay";

describe("Replay pflege", () => {
  // Fängt: eine andere Hash-Formel als beim Aufnehmen (Schlüsselreihenfolge, Leerzeichen, Unicode).
  it("reproduziert den Beleg-Hash der Aufnahme", async () => {
    expect(await belegeHash(pflege.schritte)).toBe("58a54821560309917bff750a1451c12d7065311571cdeb3901a1aae5b6b8833b");
    expect(await pruefeReplay(pflege)).toMatchObject({ ok: true });
  });

  // Fängt: ein von Hand geändertes Zitat oder eine geänderte Quelle, die trotzdem abgespielt wird.
  it("lehnt eine Aufnahme mit geändertem Zitat ab", async () => {
    const kopie = structuredClone(pflege);
    const aussage = kopie.schritte.flatMap((s) => s.antwort.aussagen)[0];
    if (!aussage) throw new Error("Fixture ohne Aussage");
    aussage.zitat += " ";
    expect(await pruefeReplay(kopie)).toEqual({ ok: false, grund: "hash" });
  });
});
