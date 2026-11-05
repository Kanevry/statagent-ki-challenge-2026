import { describe, expect, it } from "vitest";
import { sqlAuffaelligkeiten, sqlRevision as sqlRevisionBericht } from "./bericht";
import { sqlRevision as sqlRevisionLauf, sqlTreffer } from "./lauf-detail";

// Veröffentlichter Monat, später nachgerechnet: jüngster Lauf 98, veröffentlicht hat Lauf 49 (Review !51, Bank 69).
const lauf = { id: 98, quelleId: 49, lieferung: "2024-08" };

describe("Quelle der Zahlen bei einem nachgerechneten veröffentlichten Monat", () => {
  it("liest Revisionen vom jüngsten Lauf wie § 5 des Generators, sonst verschwindet sein Revisionsbedarf", () => {
    expect(sqlRevisionBericht(lauf)).toContain("v.lauf_id = 98");
    expect(sqlRevisionBericht(lauf)).not.toContain("= 49");
    expect(sqlRevisionLauf(lauf, "2024-07")).toContain("r.lauf_id = 98");
  });

  it("liest Prüftreffer vom veröffentlichenden Lauf", () => {
    expect(sqlAuffaelligkeiten(lauf)).toContain("t.lauf_id = 49");
    expect(sqlTreffer(lauf, { regelId: 7, ebene: "satz", belegSql: null })).toContain("p.lauf_id = 49");
  });
});
