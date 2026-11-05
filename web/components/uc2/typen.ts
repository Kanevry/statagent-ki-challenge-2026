import { z } from "zod";

// Ereignisvertrag des UC2-Panels (#44): jedes Ereignis hat Nummer, Runde, Art, Akteur und `daten`. Die Schemas hier
// prüfen nur, was die Oberfläche liest; unbekannte Felder bleiben erlaubt. Ein Ereignis, das nicht passt, wird
// übersprungen und gezählt, statt die Seite abstürzen zu lassen.

export const haltungSchema = z.number().int().min(-2).max(2);

const beleg = z.object({
  beleg_id: z.string(),
  medium: z.string(),
  datum: z.string().nullish(),
  monat: z.string().nullish(),
  titel: z.string().nullish(),
  pdf_seite: z.number().nullish(),
  zitat: z.string(),
});
export type Beleg = z.infer<typeof beleg>;

const zugThema = z.object({
  thema: z.string(),
  haltung: haltungSchema,
  beleg_ids: z.array(z.string()).default([]),
  bedingungen: z.array(z.string()).default([]),
  begruendung: z.string().default(""),
  zugestaendnis: z.string().nullish(),
});
export type ZugThema = z.infer<typeof zugThema>;

const zahlen = z.object({ wert: z.number(), quelle: z.string().nullish(), einheit: z.string().nullish() });
const spanne = z.object({ min: z.number(), max: z.number(), modus: z.number() });

export const daten = {
  start: z.object({
    fall: z.string().optional(),
    frage: z.string().optional(),
    stichtag: z.string().optional(),
    max_runden: z.number().optional(),
    max_akteure: z.number().optional(),
    provider: z.string().nullish(),
    belegquelle: z.string().optional(),
    modelle: z
      .record(z.string(), z.object({ modell: z.string().nullish(), provider: z.string().nullish() }))
      .optional(),
  }),
  experte: z.object({
    paket: z.string().optional(),
    beschreibung: z.string().optional(),
    entscheidend: z.string().nullish(),
    zielpruefung: z.string().optional(),
    modus_erreicht: z.boolean().optional(),
    mehrkosten_mio_eur: spanne.optional(),
    kosten_aenderung_prozent: spanne.optional(),
    wartezeit_aenderung_prozent: spanne.optional(),
  }),
  auftrag: z.object({
    ziel: z.string().optional(),
    themen: z.array(z.object({ id: z.string(), titel: z.string(), beschreibung: z.string().optional() })).default([]),
  }),
  auswahl: z.object({
    max_akteure: z.number().optional(),
    akteure: z.array(
      z.object({
        akteur: z.string(),
        belegzahl: z.number().default(0),
        eingeladen: z.boolean(),
        begruendung: z.string().default(""),
      }),
    ),
  }),
  runde: z.object({ phase: z.string().optional(), teilnehmer: z.array(z.string()).default([]) }),
  belege: z.object({ belege: z.array(beleg) }),
  zug: z.object({
    zug: z.object({
      themen: z.array(zugThema),
      zahlen: z.array(zahlen).default([]),
      bezug_auf: z.array(z.string()).default([]),
    }),
    modell: z.string().nullish(),
    provider: z.string().nullish(),
  }),
  moderatorNotiz: z.object({
    notiz: z.string(),
    widersprueche: z
      .array(z.object({ art: z.string(), thema: z.string().nullish(), akteur: z.string().nullish(), beschreibung: z.string().nullish() }))
      .default([]),
    belege_eingefordert: z.array(z.unknown()).default([]),
    haltungen_ohne_beleg: z.array(z.unknown()).default([]),
  }),
  rundeEnde: z.object({
    aenderungen: z
      .array(z.object({ runde: z.number(), thema: z.string(), akteur: z.string(), alt: z.number(), neu: z.number() }))
      .default([]),
    klassifikation: z.record(z.string(), z.string()).default({}),
    zwischenergebnis: z
      .object({ positionen: z.record(z.string(), z.record(z.string(), z.number())).default({}) })
      .partial()
      .optional(),
  }),
  zahlOhneBeleg: z.object({ fund: z.string(), thema: z.string().nullish() }),
  ergebnis: z.object({
    runden: z.number(),
    abbruch: z.string().nullish(),
    aenderungen: z
      .array(z.object({ runde: z.number(), thema: z.string(), akteur: z.string(), alt: z.number(), neu: z.number() }))
      .default([]),
    klassifikation: z.record(
      z.string(),
      z.object({
        kategorie: z.string(),
        zustimmend: z.array(z.string()).default([]),
        ablehnend: z.array(z.string()).default([]),
        enthalten: z.array(z.string()).default([]),
      }),
    ),
  }),
  abbruch: z.object({
    grund: z.string().nullish(),
    meldung: z.string().nullish(),
  }),
  ende: z.object({ status: z.string().optional(), letzte_seq: z.number().optional() }),
} as const;

export const ereignisHuelle = z.object({
  seq: z.number().int(),
  runde: z.number().int().nullish(),
  art: z.string(),
  akteur: z.string().nullish(),
  daten: z.record(z.string(), z.unknown()).default({}),
  zeit: z.string().nullish(),
});
export type Ereignis = z.infer<typeof ereignisHuelle>;

/** Alle Ereignisarten, auf die der Browser hört: EventSource braucht jeden Namen einzeln. */
export const EREIGNIS_ARTEN = [
  "start",
  "experte",
  "auftrag",
  "auswahl",
  "runde",
  "belege",
  "zug",
  "moderator_notiz",
  "runde_ende",
  "zahl_ohne_beleg",
  "ungueltige_ausgabe",
  "beleg_ungueltig",
  "zitat",
  "kontext",
  "ergebnis",
  "abbruch",
  "ende",
] as const;

/** Der Zustand, den die Oberfläche kennt: "wartet" bis das erste Ereignis da ist. */
export type FallStatus = "wartet" | "laeuft" | "fertig" | "abgebrochen";

export type Kategorie = "konsens" | "mehrheit" | "abgelehnt" | "offener_konflikt";
