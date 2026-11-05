// @vitest-environment node
import { describe, expect, it } from "vitest";
import { abbildenAntrag } from "./antrag";
import pflege from "./fixtures/pflege.json";
import { belegeHash, pruefeReplay } from "./replay";

describe("Replay pflege", () => {
  // Fängt: eine andere Hash-Formel als beim Aufnehmen (Schlüsselreihenfolge, Leerzeichen, Unicode).
  it("reproduziert den Beleg-Hash der Aufnahme", async () => {
    expect(await belegeHash(pflege.schritte)).toBe("6fc3d78272351ae09a1ec0d005542ba461112e77848e67fd9773756ff3afac08");
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

describe("Aussagen der Aufnahme", () => {
  // Fängt: eine Aussage, die eine Schwelle aus dem Wortlaut verschärft oder weglässt („ab 65 Stunden“ statt „mehr als
  // 65 Stunden“, „bei sechs Monaten“ statt „voraussichtlich mindestens sechs Monate“); die Jury sieht sie online.
  const EINSCHRAENKUNGEN = ["mehr als", "weniger als", "mindestens", "höchstens", "voraussichtlich"];
  const aussagen = pflege.schritte.flatMap((s) => s.antwort.aussagen);

  it("übernimmt jede Einschränkung aus dem Zitat in den Aussagetext", () => {
    expect(aussagen.length).toBeGreaterThan(0);
    for (const a of aussagen) {
      for (const wort of EINSCHRAENKUNGEN) {
        if (a.zitat.toLowerCase().includes(wort)) expect(a.text.toLowerCase(), `${a.text} | ${wort}`).toContain(wort);
      }
    }
  });
});
