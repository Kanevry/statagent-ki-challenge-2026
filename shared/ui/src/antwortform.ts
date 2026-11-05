import { z } from "zod";

// Antwortform `UcAntwort` der UC4-Kette (#96). Quelle der Wahrheit ist das aus pydantic erzeugte JSON-Schema
// `shared/schema/uc-antwort.json` (`plattform.antwortform`); tests/antwortform.test.ts prüft die Fixture.
// Bewusst ohne "use client": Route-Handler importieren das Schema serverseitig.

export const ucs = ["uc1", "uc2", "uc3"] as const;

/** Herkunft einer Aussage, nie erfunden. */
export const belegSchema = z
  .object({
    quelle: z.string(),
    lieferung: z.string().nullable(),
    monat: z.string().nullable(),
    sql: z.string().nullable(),
    ref: z.string().nullable(),
  })
  .strict();

/** Eine Zahl der Antwort; `beleg` ist der Index in `belege`. */
export const zahlSchema = z
  .object({
    bezeichnung: z.string(),
    wert: z.number(),
    einheit: z.string().nullable(),
    beleg: z.number().int(),
  })
  .strict();

export const ucAntwortSchema = z
  .object({
    text: z.string(),
    belege: z.array(belegSchema),
    zahlen: z.array(zahlSchema),
    uc: z.enum(ucs),
    modell: z.string().nullable(),
    protokoll_id: z.number().int().nullable(),
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
