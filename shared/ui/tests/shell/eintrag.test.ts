import { z } from "zod";
import fixture from "../../../schema/fixtures/protokoll-eintraege.json";
import jsonSchema from "../../../schema/protokoll-eintrag.json";
import { eintraegeSchema, eintragSchema } from "../../src/shell/eintrag";

// Contract-Test Vertrag H: das zod-Schema der Schublade muss dem aus pydantic erzeugten JSON-Schema entsprechen.
// Fehlerbild, das er fängt: Python erweitert oder ändert `Eintrag`, die Oberfläche liest still das alte Format.

type Teil = { type?: string | string[]; enum?: string[]; format?: string; anyOf?: Teil[] };

function form(teil: Teil) {
  const varianten = teil.anyOf ?? [teil];
  return {
    // `anyOf: [{type: "string"}, {type: "null"}]` (pydantic) und `type: ["string", "null"]` (zod) sind gleichwertig.
    typen: varianten.flatMap((v) => (Array.isArray(v.type) ? v.type : [v.type])).sort(),
    werte: varianten.flatMap((v) => v.enum ?? []).sort(),
    format: varianten.find((v) => v.format)?.format ?? null,
  };
}

function formen(schema: { properties: Record<string, Teil> }) {
  return Object.fromEntries(Object.entries(schema.properties).map(([name, teil]) => [name, form(teil)]));
}

describe("Eintrag (zod) gegen shared/schema", () => {
  it("die Fixture erfüllt den Vertrag", () => {
    expect(eintraegeSchema.safeParse(fixture).error?.issues ?? []).toEqual([]);
  });

  it("Felder, Typen, Nullbarkeit und Aufzählungen entsprechen dem JSON-Schema", () => {
    const ausZod = z.toJSONSchema(eintragSchema) as { properties: Record<string, Teil>; required: string[]; additionalProperties: unknown };
    expect(formen(ausZod)).toEqual(formen(jsonSchema as { properties: Record<string, Teil> }));
    expect([...ausZod.required].sort()).toEqual([...jsonSchema.required].sort());
    expect(ausZod.additionalProperties).toBe(jsonSchema.additionalProperties);
  });

  it("weist unbekannte und fehlende Felder ab", () => {
    const basis = fixture[0]!;
    expect(eintragSchema.safeParse({ ...basis, neu: 1 }).success).toBe(false);
    const { wirkung: _weg, ...ohneWirkung } = basis;
    expect(eintragSchema.safeParse(ohneWirkung).success).toBe(false);
    expect(eintragSchema.safeParse({ ...basis, zeit: "2026-11-05 09:12" }).success).toBe(false);
  });
});
