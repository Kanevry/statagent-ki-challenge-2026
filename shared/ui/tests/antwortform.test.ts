import fixture from "../../schema/fixtures/uc-antwort.json";
import { ucAntwortSchema } from "../src/antwortform";

// Contract-Test #96: die Fixture aus shared/schema erfüllt den zod-Vertrag, ein Beleg-Index ins Leere nicht.

describe("UcAntwort (zod) gegen shared/schema", () => {
  it("die Fixture erfüllt den Vertrag", () => {
    expect(ucAntwortSchema.safeParse(fixture).error?.issues ?? []).toEqual([]);
  });

  it("weist eine Zahl mit ungültigem Beleg-Index ab", () => {
    const zahl = { ...fixture.zahlen[0]!, beleg: 1 };
    const ergebnis = ucAntwortSchema.safeParse({ ...fixture, zahlen: [zahl] });
    expect(ergebnis.error?.issues.map((i) => i.path)).toEqual([["zahlen", 0, "beleg"]]);
  });
});
