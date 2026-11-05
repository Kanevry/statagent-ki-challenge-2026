import { lies, type Lesung, type Sql } from "./db";
import type { Ergebnisstand, Lauf, Monatslauf } from "./typen";

/**
 * Welcher Lauf für einen Monat gilt: der jüngste veröffentlichte, sonst der jüngste erfolgreiche. Gleiche Regel wie
 * `statagent.ergebnis.letzter_lauf` (uc3/), damit Seite, Sheet und Qualitätsbericht dieselben Zahlen zeigen.
 * Abgebrochene oder laufende Läufe zählen nie.
 */
export const MASSGEBLICH_SQL = `SELECT DISTINCT ON (lieferung) *
FROM meta.lauf
WHERE regelsatz = $1 AND status IN ('fertig', 'unveraendert')
ORDER BY lieferung, (ergebnis_status = 'endgueltig') DESC, id DESC`;

/** Zeile aus meta.lauf, wie postgres.js sie liefert (bigint als Text, Zeitpunkte als Date). */
export interface LaufZeile {
  id: number;
  lieferung: string;
  regelsatz: string;
  regelstand: string | null;
  status: string;
  ergebnis_status: string | null;
  gelesen: string | number | null;
  gezaehlt: string | number | null;
  nicht_gezaehlt: string | number | null;
  ausgeschlossen: string | number | null;
  fortgeschrieben: string | number | null;
  ergebnis_hash: string | null;
  gestartet_am: Date | string;
  beendet_am: Date | string | null;
  meldung: string | null;
  freigegeben_von: string | null;
  freigegeben_am: Date | string | null;
}

export interface MonatslaufZeile extends LaufZeile {
  laeufe_gesamt: string | number;
  angehalten: boolean | null;
  anhaltende_regeln: string[] | null;
  auffaelligkeiten: string | number | null;
  nicht_erklaerbar: string | number | null;
}

function zahl(wert: string | number | null | undefined): number {
  const n = Number(wert ?? 0);
  return Number.isFinite(n) ? n : 0;
}

function iso(wert: Date | string | null): string | null {
  if (wert === null) return null;
  return wert instanceof Date ? wert.toISOString() : new Date(wert).toISOString();
}

export function laufAus(z: LaufZeile): Lauf {
  const stand: Ergebnisstand = z.ergebnis_status === "endgueltig" ? "endgueltig" : "vorlaeufig";
  return {
    id: z.id,
    lieferung: z.lieferung,
    regelsatz: z.regelsatz,
    regelstand: z.regelstand ?? "",
    status: z.status,
    ergebnisStand: stand,
    gelesen: zahl(z.gelesen),
    gezaehlt: zahl(z.gezaehlt),
    nichtGezaehlt: zahl(z.nicht_gezaehlt),
    ausgeschlossen: zahl(z.ausgeschlossen),
    fortgeschrieben: zahl(z.fortgeschrieben),
    ergebnisHash: z.ergebnis_hash ?? "",
    gestartetAm: iso(z.gestartet_am) ?? "",
    beendetAm: iso(z.beendet_am),
    meldung: z.meldung,
    freigegebenVon: z.freigegeben_von,
    freigegebenAm: iso(z.freigegeben_am),
  };
}

export function monatslaufAus(z: MonatslaufZeile): Monatslauf {
  return {
    ...laufAus(z),
    laeufeGesamt: zahl(z.laeufe_gesamt),
    angehalten: Boolean(z.angehalten),
    anhaltendeRegeln: z.anhaltende_regeln ?? [],
    auffaelligkeiten: zahl(z.auffaelligkeiten),
    nichtErklaerbar: zahl(z.nicht_erklaerbar),
  };
}

/** Abrechnung eines Laufs: Sätze aus der Lieferung = gezählt (ohne Fortgeschriebene) + nicht gezählt + ausgeschlossen. */
export function abrechnung(lauf: Lauf): { ausLieferung: number; gehtAuf: boolean } {
  const ausLieferung = lauf.gezaehlt - lauf.fortgeschrieben;
  return { ausLieferung, gehtAuf: lauf.gelesen === ausLieferung + lauf.nichtGezaehlt + lauf.ausgeschlossen };
}

/** Alle Monate mit ihrem maßgeblichen Lauf, aufsteigend nach Monat. */
export async function ladeMonatslaeufe(sql: Sql, regelsatz = "v1"): Promise<Monatslauf[]> {
  const zeilen = await sql<MonatslaufZeile[]>`
    WITH massgeblich AS (
      SELECT DISTINCT ON (lieferung) *
      FROM meta.lauf
      WHERE regelsatz = ${regelsatz} AND status IN ('fertig', 'unveraendert')
      ORDER BY lieferung, (ergebnis_status = 'endgueltig') DESC, id DESC
    )
    SELECT m.*,
           (SELECT count(*) FROM meta.lauf a WHERE a.lieferung = m.lieferung AND a.regelsatz = m.regelsatz) AS laeufe_gesamt,
           t.angehalten, t.anhaltende_regeln, t.auffaelligkeiten, t.nicht_erklaerbar
    FROM massgeblich m
    LEFT JOIN LATERAL (
      SELECT bool_or(p.anhalten) AS angehalten,
             array_agg(r.name ORDER BY r.name) FILTER (WHERE p.anhalten) AS anhaltende_regeln,
             count(*) FILTER (WHERE p.anzahl > 0) AS auffaelligkeiten,
             count(*) FILTER (WHERE p.anzahl > 0 AND p.einstufung = 'nicht-erklaerbar') AS nicht_erklaerbar
      FROM meta.pruefung_treffer p
      JOIN meta.regel r ON r.id = p.regel_id
      WHERE p.lauf_id = m.id
    ) t ON true
    ORDER BY m.lieferung`;
  return zeilen.map(monatslaufAus);
}

/** Der maßgebliche Lauf eines Monats oder `null`. */
export async function ladeMassgeblichenLauf(sql: Sql, lieferung: string, regelsatz = "v1"): Promise<Lauf | null> {
  const [zeile] = await sql<LaufZeile[]>`
    SELECT * FROM meta.lauf
    WHERE lieferung = ${lieferung} AND regelsatz = ${regelsatz} AND status IN ('fertig', 'unveraendert')
    ORDER BY (ergebnis_status = 'endgueltig') DESC, id DESC
    LIMIT 1`;
  return zeile ? laufAus(zeile) : null;
}

/** Wie viele aktive Regeln eines Regelsatzes es gibt und wie viele davon noch keine Freigabe mit Namen haben. */
export async function ladeRegelFreigaben(sql: Sql, regelsatz = "v1"): Promise<{ aktiv: number; ohneFreigabe: number }> {
  const [z] = await sql<{ aktiv: string; ohne_freigabe: string }[]>`
    SELECT count(*) AS aktiv, count(*) FILTER (WHERE freigegeben_von IS NULL) AS ohne_freigabe
    FROM meta.regel WHERE regelsatz = ${regelsatz} AND aktiv`;
  return { aktiv: zahl(z?.aktiv), ohneFreigabe: zahl(z?.ohne_freigabe) };
}

/** SQL der Regel-Zählung, wie der Beleg sie zeigt. */
export function sqlRegelFreigaben(regelsatz = "v1"): string {
  return [
    "SELECT count(*) AS aktiv, count(*) FILTER (WHERE freigegeben_von IS NULL) AS ohne_freigabe",
    `FROM meta.regel WHERE regelsatz = '${regelsatz.replaceAll("'", "''")}' AND aktiv;`,
  ].join("\n");
}

/** Bequemer Einstieg für Seiten: Monatsläufe samt Regel-Freigaben oder Grund für den Leerzustand. */
export function leseMonatsuebersicht(
  regelsatz = "v1",
): Promise<Lesung<{ monate: Monatslauf[]; regeln: { aktiv: number; ohneFreigabe: number } }>> {
  return lies(async (sql) => {
    const [monate, regeln] = await Promise.all([ladeMonatslaeufe(sql, regelsatz), ladeRegelFreigaben(sql, regelsatz)]);
    return { monate, regeln };
  });
}
