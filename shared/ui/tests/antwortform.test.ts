import { z } from "zod";
import fixture from "../../schema/fixtures/uc-antwort.json";
import jsonSchema from "../../schema/uc-antwort.json";
import { belegSchema, ucAntwortSchema, zahlSchema } from "../src/antwortform";

// Contract-Test #96: das zod-Schema muss dem aus pydantic erzeugten JSON-Schema entsprechen (Felder, Typen,
// Nullbarkeit, Pflichtfelder, Aufzählungen), je Objekt über $defs. Fehlerbild, das er fängt: Python erweitert
// oder ändert `UcAntwort`, die Oberfläche liest still das alte Format.

type Teil = { type?: string | string[]; enum?: string[]; anyOf?: Teil[]; $ref?: string; items?: Teil };
type Objekt = { properties: Record<string, Teil>; required?: string[]; additionalProperties?: unknown };

function form(teil: Teil) {
  const varianten = teil.anyOf ?? [teil];
  return {
    // `anyOf: [{type: "string"}, {type: "null"}]` (pydantic) und `type: ["string", "null"]` (zod) sind gleichwertig;
    // Verweise auf $defs (pydantic) und eingebettete Objekte (zod) zählen beide als „object“.
    typen: varianten
      .flatMap((v) => (v.$ref ? ["object"] : Array.isArray(v.type) ? v.type : [v.type]))
      .sort(),
    werte: varianten.flatMap((v) => v.enum ?? []).sort(),
  };
}

function vergleiche(ausZod: Objekt, ausPython: Objekt) {
  const formen = (o: Objekt) => Object.fromEntries(Object.entries(o.properties).map(([n, t]) => [n, form(t)]));
  expect(formen(ausZod)).toEqual(formen(ausPython));
  expect([...(ausZod.required ?? [])].sort()).toEqual([...(ausPython.required ?? [])].sort());
  expect(ausZod.additionalProperties).toBe(ausPython.additionalProperties);
}

const defs = (jsonSchema as unknown as { $defs: Record<string, Objekt> }).$defs;

describe("UcAntwort (zod) gegen shared/schema", () => {
  it("die Fixture erfüllt den Vertrag", () => {
    expect(ucAntwortSchema.safeParse(fixture).error?.issues ?? []).toEqual([]);
  });

  it.each([
    ["Beleg", belegSchema],
    ["Zahl", zahlSchema],
  ] as const)("%s entspricht $defs im JSON-Schema", (name, schema) => {
    vergleiche(z.toJSONSchema(schema) as unknown as Objekt, defs[name]!);
  });

  it("UcAntwort entspricht dem JSON-Schema", () => {
    vergleiche(z.toJSONSchema(ucAntwortSchema) as unknown as Objekt, jsonSchema as unknown as Objekt);
  });

  it("weist eine Zahl mit ungültigem Beleg-Index ab", () => {
    const zahl = { ...fixture.zahlen[0]!, beleg: 1 };
    const ergebnis = ucAntwortSchema.safeParse({ ...fixture, zahlen: [zahl] });
    expect(ergebnis.error?.issues.map((i) => i.path)).toEqual([["zahlen", 0, "beleg"]]);
  });

  it.each([["412.345"], [Number.NaN], [Number.POSITIVE_INFINITY], [true]])("weist wert=%s ab", (wert) => {
    const zahl = { ...fixture.zahlen[0]!, wert };
    expect(ucAntwortSchema.safeParse({ ...fixture, zahlen: [zahl] }).success).toBe(false);
  });
});
