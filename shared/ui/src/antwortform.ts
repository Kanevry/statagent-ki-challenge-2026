import { z } from "zod";

// Antwortform `UcAntwort` der UC4-Kette (#96). Quelle der Wahrheit ist das aus pydantic erzeugte JSON-Schema
// `shared/schema/uc-antwort.json` (`plattform.antwortform`); tests/antwortform.test.ts vergleicht beide Formen.
// Bewusst ohne "use client": Route-Handler importieren das Schema serverseitig.
// Felder mit `.nullable().optional()` dürfen fehlen oder null sein (pydantic: `= None`).

export const ucs = ["uc1", "uc2", "uc3"] as const;
/** Stand einer UC3-Zahl: `vorlaeufig`, solange der Monat noch revidiert werden kann. */
export const staende = ["endgueltig", "vorlaeufig"] as const;

const optionalerText = z.string().nullable().optional();

/** Herkunft einer Aussage, nie erfunden; `uc` ist der UC, der den Beleg geliefert hat. */
export const belegSchema = z
  .object({
    uc: z.enum(ucs),
    quelle: z.string(),
    lieferung: optionalerText,
    monat: optionalerText,
    sql: optionalerText,
    ref: optionalerText,
    /** UC3: Version des Regelsatzes aus `meta.regel` */
    regelstand: optionalerText,
    /** UC3: `meta.lauf.ergebnis_hash` */
    lauf: optionalerText,
    stand: z.enum(staende).nullable().optional(),
  })
  .strict();

/** Eine Zahl der Antwort; `wert` ist endlich (zod lehnt NaN und Infinity ab), `beleg` der Index in `belege`. */
export const zahlSchema = z
  .object({
    bezeichnung: z.string(),
    wert: z.union([z.number().int(), z.number()]),
    einheit: optionalerText,
    beleg: z.number().int(),
  })
  .strict();

export const ucAntwortSchema = z
  .object({
    text: z.string(),
    belege: z.array(belegSchema),
    zahlen: z.array(zahlSchema),
    uc: z.enum(ucs),
    modell: optionalerText,
    protokoll_id: z.number().int().nullable().optional(),
  })
  .strict()
  .superRefine((antwort, ctx) => {
    antwort.zahlen.forEach((zahl, nummer) => {
      if (zahl.beleg < 0 || zahl.beleg >= antwort.belege.length) {
        ctx.addIssue({
          code: "custom",
          path: ["zahlen", nummer, "beleg"],
          message: `zahlen[${nummer}].beleg=${zahl.beleg} zeigt auf keinen Beleg (${antwort.belege.length} vorhanden)`,
        });
      }
    });
  });

export type Beleg = z.infer<typeof belegSchema>;
export type Zahl = z.infer<typeof zahlSchema>;
export type UcAntwort = z.infer<typeof ucAntwortSchema>;
