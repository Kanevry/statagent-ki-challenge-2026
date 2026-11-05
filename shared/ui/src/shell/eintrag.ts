import { z } from "zod";

// JSON-Vertrag `Eintrag` für GET /api/<uc>/protokoll (Vertrag H). Quelle der Wahrheit ist das aus pydantic
// erzeugte JSON-Schema `shared/schema/protokoll-eintrag.json`; tests/shell/eintrag.test.ts hält beide gleich.
// Bewusst ohne "use client": Route-Handler importieren das Schema serverseitig.

export const akteure = ["agent", "mensch"] as const;
export const eintragStatus = ["offen", "freigegeben", "abgelehnt"] as const;

export const eintragSchema = z
  .object({
    id: z.number().int(),
    zeit: z.iso.datetime({ offset: true }),
    uc: z.string(),
    akteur: z.enum(akteure),
    name: z.string(),
    anweisung: z.string(),
    wirkung: z.string().nullable(),
    status: z.enum(eintragStatus),
    modell: z.string().nullable(),
    ref: z.string().nullable(),
  })
  .strict();

/** Antwort von GET /api/<uc>/protokoll: Liste, neueste zuerst. */
export const eintraegeSchema = z.array(eintragSchema);

export type Eintrag = z.infer<typeof eintragSchema>;
export type Akteur = Eintrag["akteur"];
export type EintragStatus = Eintrag["status"];
