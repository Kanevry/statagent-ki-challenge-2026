import postgres from "postgres";
import { befundeAusFixture } from "./befunde-fixture";
import { zahl, type Einstufung } from "./fakten";
import type { BefundTabelle, BefundZeile } from "./typen";

/**
 * Tabelle „Gefundene Datenfehler“: lesend aus meta.pruefung_treffer der UC3-Datenbank (UC3_DATABASE_URL).
 * Ohne Datenbank, bei Timeout oder ohne Treffer: die 8 Befunde der Gegenrechnung als „Beispieldaten“.
 * Nur serverseitig importieren (postgres.js).
 */

const ZEITLIMIT_MS = 2_500;

/** Verbindung steht, aber die Prüfung hat noch keine Treffer geschrieben: kein Defekt, nur noch kein Lauf. */
class KeineTreffer extends Error {}
const MAX_ZEILEN = 50;

const EINSTUFUNG_TEXT: Record<string, string> = {
  "erklaert-plausibel": "erklärt, plausibel",
  "erklaert-datenproblem": "erklärt, Datenproblem",
  "nicht-erklaerbar": "nicht erklärbar",
};

interface TrefferRoh {
  anzahl: string | number;
  umfang: string | null;
  einstufung: string | null;
  beleg_sql: string | null;
  anhalten: boolean;
  /** Ganze Zeile aus meta.lauf und meta.regel als JSON, damit die Seite nicht an deren Spaltennamen hängt. */
  lauf: Record<string, unknown> | null;
  regel: Record<string, unknown> | null;
}

function text(o: Record<string, unknown> | null, ...schluessel: string[]): string | undefined {
  if (!o) return undefined;
  for (const k of schluessel) {
    const v = o[k];
    if (typeof v === "string" && v.trim()) return v.trim();
    if (typeof v === "number") return String(v);
  }
  return undefined;
}

export function zeileAusTreffer(t: TrefferRoh): BefundZeile {
  const bekannt = t.einstufung && t.einstufung in EINSTUFUNG_TEXT;
  // Ohne Einstufung gilt der Treffer als nicht eingestuft; in der Tabelle steht er wie „nicht erklärbar“ markiert.
  const einstufung = (bekannt ? t.einstufung : "nicht-erklaerbar") as Einstufung;
  const einstufungText = bekannt ? EINSTUFUNG_TEXT[t.einstufung as string] : "nicht eingestuft";
  const beleg = t.beleg_sql?.split("\n").find((z) => z.trim())?.trim().slice(0, 80);
  return {
    befund:
      text(t.regel, "name", "titel", "bezeichnung", "beschreibung", "kurz", "code") ?? "Prüfregel ohne Namen",
    lieferung: text(t.lauf, "lieferung", "lieferung_id", "monat") ?? "unbekannt",
    saetze: t.umfang?.trim() || zahl(Number(t.anzahl)),
    einstufung,
    einstufungText: t.anhalten ? `${einstufungText} · Lauf angehalten` : einstufungText,
    beleg,
  };
}

async function ausDatenbank(url: string, stand: string): Promise<BefundTabelle> {
  const sql = postgres(url, { max: 1, connect_timeout: 2, idle_timeout: 5, prepare: false, onnotice: () => {} });
  try {
    const abfrage = (async () => {
      const [zeilen, [{ anzahl }]] = await Promise.all([
        sql<TrefferRoh[]>`
          select t.anzahl, t.umfang, t.einstufung, t.beleg_sql, t.anhalten,
                 to_jsonb(l) as lauf, to_jsonb(r) as regel
            from meta.pruefung_treffer t
            left join meta.lauf l on l.id = t.lauf_id
            left join meta.regel r on r.id = t.regel_id
           -- Nur echte Funde (Jury-Kritik 05.11.: „P01 … 0 Zeilen · nicht eingestuft“ stand oben). Was den Lauf
           -- anhält und nicht erklärbar ist zuerst, dann die größten; nicht Eingestuftes zuletzt.
           where t.anzahl > 0
           order by t.anhalten desc nulls last, (t.einstufung = 'nicht-erklaerbar') desc nulls last,
                    (t.einstufung is null), t.anzahl desc
           limit ${MAX_ZEILEN}`,
        sql<{ anzahl: string }[]>`select count(*)::text as anzahl from meta.pruefung_treffer where anzahl > 0`,
      ]);
      return { zeilen, anzahl: Number(anzahl) };
    })();
    let zeitgeber: ReturnType<typeof setTimeout> | undefined;
    const zeitlimit = new Promise<never>((_, ablehnen) => {
      zeitgeber = setTimeout(() => ablehnen(new Error(`Zeitlimit ${ZEITLIMIT_MS} ms`)), ZEITLIMIT_MS);
    });
    const ergebnis = await Promise.race([abfrage, zeitlimit]).finally(() => clearTimeout(zeitgeber));
    if (ergebnis.anzahl === 0) throw new KeineTreffer("meta.pruefung_treffer ist leer");
    return { quelle: "datenbank", zeilen: ergebnis.zeilen.map(zeileAusTreffer), anzahl: ergebnis.anzahl, stand };
  } finally {
    await sql.end({ timeout: 1 }).catch(() => {});
  }
}

/** Wie lange ein Stand aus der Datenbank gilt; die Seite rendert je Anfrage, die Datenbank sieht höchstens eine je Minute. */
export const ZWISCHENSPEICHER_MS = 60_000;
let zwischenspeicher: { url: string; bis: number; tabelle: BefundTabelle } | null = null;

/** Nur für Tests: vergisst den gemerkten Stand. */
export function befundeZwischenspeicherLeeren(): void {
  zwischenspeicher = null;
}

export async function ladeBefunde(jetzt: number = Date.now()): Promise<BefundTabelle> {
  const url = process.env.UC3_DATABASE_URL;
  if (url && zwischenspeicher && zwischenspeicher.url === url && zwischenspeicher.bis > jetzt) {
    return zwischenspeicher.tabelle;
  }
  const tabelle = await ladeFrisch(url);
  // Nur einen Stand aus der Datenbank merken: Fällt sie aus, versucht die nächste Anfrage es wieder.
  if (url && tabelle.quelle === "datenbank") zwischenspeicher = { url, bis: jetzt + ZWISCHENSPEICHER_MS, tabelle };
  return tabelle;
}

async function ladeFrisch(url: string | undefined): Promise<BefundTabelle> {
  const stand = new Date().toISOString();
  if (!url) {
    console.warn("[landing] UC3_DATABASE_URL fehlt, zeige Beispieldaten");
    return befundeAusFixture(stand);
  }
  try {
    return await ausDatenbank(url, stand);
  } catch (fehler) {
    if (fehler instanceof KeineTreffer) {
      console.warn("[landing] meta.pruefung_treffer ist leer, zeige Beispieldaten");
      return befundeAusFixture(stand, "keine-treffer");
    }
    // Nur die Meldung, nie die Verbindungs-URL (enthält das Passwort).
    const grund = fehler instanceof Error ? fehler.message.replaceAll(url, "<UC3_DATABASE_URL>") : "unbekannt";
    console.warn("[landing] UC3-Datenbank nicht verfügbar, zeige Beispieldaten:", grund);
    return befundeAusFixture(stand);
  }
}
