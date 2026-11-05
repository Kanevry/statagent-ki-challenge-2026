import { eintraegeSchema, eintragStatus, type Eintrag } from "@kic/ui/shell";
import { ucs, type UcId } from "@kic/ui/ucs";
import { z } from "zod";
import fixture from "../../../shared/schema/fixtures/protokoll-eintraege.json";

// Referenz für GET /api/<uc>/protokoll. Der Fallback-Handler web/app/api/[uc]/protokoll/route.ts liefert damit
// in Entwicklung die Fixture, in Produktion eine leere Liste (die Schublade zeigt dann ihren Leerzustand), bis
// ein UC seinen eigenen Handler unter web/app/api/<uc>/protokoll/route.ts anlegt. Ein echter Handler ersetzt
// nur `quelle` (Datenbank lesend oder UC-CLI mit --json) und behält Prüfung und Antwortform.

/** Fixture beim Laden gegen den Vertrag geprüft: eine kaputte Fixture fällt sofort auf. */
export const fixtureEintraege: Eintrag[] = eintraegeSchema.parse(fixture);

const statusParam = z.enum(eintragStatus);

/**
 * Darf der Fallback die Fixture zeigen? Nur außerhalb von Produktion oder mit `KIC_FIXTURE=1`: erfundene
 * Einträge dürfen vor der Jury nie wie ein echtes Protokoll aussehen.
 */
export function fixtureErlaubt(umgebung: Readonly<Record<string, string | undefined>> = process.env): boolean {
  return umgebung.NODE_ENV !== "production" || umgebung.KIC_FIXTURE === "1";
}

/** Standardquelle des Fallbacks: Fixture nur, wenn `fixtureErlaubt()`, sonst nichts. */
export const fallbackQuelle = (): readonly Eintrag[] => (fixtureErlaubt() ? fixtureEintraege : []);

export function istUcId(wert: string): wert is UcId {
  return ucs.some((uc) => uc.id === wert);
}

/** Einträge eines UC, optional nach Status, neueste zuerst (wie `plattform.protokoll.lies`). */
export function filtereEintraege(eintraege: readonly Eintrag[], uc: UcId, status?: Eintrag["status"]): Eintrag[] {
  return eintraege
    .filter((e) => e.uc === uc && (status === undefined || e.status === status))
    .sort((a, b) => b.id - a.id);
}

/** Baut die Antwort für GET /api/<uc>/protokoll[?status=offen|freigegeben|abgelehnt]. */
export async function protokollAntwort(
  anfrage: Request,
  uc: string,
  quelle: (uc: UcId) => Promise<readonly Eintrag[]> | readonly Eintrag[] = fallbackQuelle,
): Promise<Response> {
  if (!istUcId(uc)) return Response.json({ fehler: `Unbekannter Bereich: ${uc}` }, { status: 404 });
  const roh = new URL(anfrage.url).searchParams.get("status");
  const status = roh === null ? undefined : statusParam.safeParse(roh);
  if (status && !status.success) {
    return Response.json({ fehler: `status muss ${eintragStatus.join(", ")} sein` }, { status: 400 });
  }
  const eintraege = eintraegeSchema.parse(filtereEintraege(await quelle(uc), uc, status?.data));
  return Response.json(eintraege, { headers: { "cache-control": "no-store" } });
}
