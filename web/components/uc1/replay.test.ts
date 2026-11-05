// @vitest-environment node
import { describe, expect, it } from "vitest";
import { abbildenAntrag } from "./antrag";
import pflege from "./fixtures/pflege.json";
import { belegeHash, pruefeReplay } from "./replay";

describe("Replay pflege", () => {
  // Fängt: eine andere Hash-Formel als beim Aufnehmen (Schlüsselreihenfolge, Leerzeichen, Unicode).
  it("reproduziert den Beleg-Hash der Aufnahme", async () => {
    expect(await belegeHash(pflege.schritte)).toBe("b38d3156c128d5cfa43fe57ecb3eef31abf0c2b9ebf21318b10d137739c207c7");
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

  // Fängt: ein Replay-Schema, das den Antrag verwirft (Feld fehlt im Schema) oder an der Abbildung scheitert, und
  // einen Antrag aus einer anderen Sitzung als das Gespräch der Aufnahme.
  it("trägt den Antrag derselben Sitzung, und er bildet ab", async () => {
    const pruefung = await pruefeReplay(pflege);
    if (!pruefung.ok) throw new Error("Aufnahme ungültig");
    const antrag = abbildenAntrag(pruefung.replay.antrag);
    expect(antrag?.sitzung_id).toBe(pruefung.replay.schritte.at(-1)?.antwort.sitzung_id);
    expect(antrag?.befuellt).toContainEqual({ feld: "Vorname", wert: "Maria" });
  });
});
