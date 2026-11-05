import { z } from "zod";
import { rohAntragSchema } from "./antrag";
import { webAntwortSchema, type WebAntwort } from "./antwort";

// Replay (#35): ein echt aufgezeichneter Durchlauf des Lotsen, ohne Netz abgespielt. Die Aufnahme trägt einen
// SHA-256 über die Zitat-Belege der Aussagen (Zitat, Quelle, Stand), nicht über `traeger` und nicht über `antrag`; die Seite rechnet ihn beim Abspielen nach und zeigt bei
// Abweichung keine Antwort, damit niemand ein von Hand geändertes Zitat für eine Quelle hält. `antrag` ist die rohe
// Ausgabe von `lotse antrag … --json` derselben Sitzung (ohne `pdf`); sie läuft durch dieselbe Abbildung wie live.
// Alle Personenangaben der Aufnahme sind erfunden.

export const replaySchema = z.object({
  szenario: z.string(),
  /** ISO-Zeitpunkt der Aufnahme. */
  aufgenommen: z.string(),
  /** Wie aufgenommen wurde (Befehl, Kern-Stand, Provider). */
  quelle: z.string(),
  schritte: z
    .array(
      z.object({
        eingabe: z.object({
          text: z.string(),
          stil: z.enum(["standard", "einfach"]).optional(),
          sprache: z.enum(["de", "en"]).optional(),
        }),
        antwort: webAntwortSchema,
      }),
    )
    .min(1),
  belege_sha256: z.string().regex(/^[0-9a-f]{64}$/),
  antrag: rohAntragSchema.optional(),
});
export type Replay = z.infer<typeof replaySchema>;
export type ReplaySchritt = Replay["schritte"][number];

/** Text, über den der Hash läuft: alle Aussagen aller Schritte in Reihenfolge, je Zitat, Quelle, Stand. */
export function belegeText(schritte: ReadonlyArray<{ antwort: Pick<WebAntwort, "aussagen"> }>): string {
  return JSON.stringify(
    schritte.map((s) => s.antwort.aussagen.map((a) => ({ zitat: a.zitat, quelle: a.quelle, stand: a.stand }))).flat(),
  );
}

/** SHA-256 als Hex über `belegeText`, mit Web Crypto (Browser und Node). */
export async function belegeHash(schritte: ReadonlyArray<{ antwort: Pick<WebAntwort, "aussagen"> }>): Promise<string> {
  const daten = new TextEncoder().encode(belegeText(schritte));
  const summe = await globalThis.crypto.subtle.digest("SHA-256", daten);
  return Array.from(new Uint8Array(summe), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export type ReplayPruefung = { ok: true; replay: Replay } | { ok: false; grund: "format" | "hash" };

/** Prüft Form und Beleg-Hash einer Aufnahme. */
export async function pruefeReplay(roh: unknown): Promise<ReplayPruefung> {
  const geprueft = replaySchema.safeParse(roh);
  if (!geprueft.success) return { ok: false, grund: "format" };
  const hash = await belegeHash(geprueft.data.schritte);
  return hash === geprueft.data.belege_sha256 ? { ok: true, replay: geprueft.data } : { ok: false, grund: "hash" };
}

/** „2026-11-05T14:03:00Z“ → „5. November 2026“ (Wiener Zeit); Ungültiges bleibt, wie es ist. */
export function formatAufnahme(iso: string): string {
  const datum = new Date(iso);
  if (Number.isNaN(datum.getTime())) return iso;
  return new Intl.DateTimeFormat("de-AT", { dateStyle: "long", timeZone: "Europe/Vienna" }).format(datum);
}
