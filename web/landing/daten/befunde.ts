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
  // Ohne Einstufung gilt der Treffer als offen; in der Tabelle steht er wie „nicht erklärbar“ markiert.
  const einstufung = (bekannt ? t.einstufung : "nicht-erklaerbar") as Einstufung;
  const einstufungText = bekannt ? EINSTUFUNG_TEXT[t.einstufung as string] : "offen";
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
           order by (t.einstufung = 'nicht-erklaerbar') desc nulls first, t.anzahl desc
           limit ${MAX_ZEILEN}`,
        sql<{ anzahl: string }[]>`select count(*)::text as anzahl from meta.pruefung_treffer`,
      ]);
      return { zeilen, anzahl: Number(anzahl) };
    })();
    let zeitgeber: ReturnType<typeof setTimeout> | undefined;
    const zeitlimit = new Promise<never>((_, ablehnen) => {
      zeitgeber = setTimeout(() => ablehnen(new Error(`Zeitlimit ${ZEITLIMIT_MS} ms`)), ZEITLIMIT_MS);
    });
    const ergebnis = await Promise.race([abfrage, zeitlimit]).finally(() => clearTimeout(zeitgeber));
    if (ergebnis.anzahl === 0) throw new Error("meta.pruefung_treffer ist leer");
    return { quelle: "datenbank", zeilen: ergebnis.zeilen.map(zeileAusTreffer), anzahl: ergebnis.anzahl, stand };
  } finally {
    await sql.end({ timeout: 1 }).catch(() => {});
  }
}

export async function ladeBefunde(): Promise<BefundTabelle> {
  const stand = new Date().toISOString();
  const url = process.env.UC3_DATABASE_URL;
  if (!url) {
    console.warn("[landing] UC3_DATABASE_URL fehlt, zeige Beispieldaten");
    return befundeAusFixture(stand);
  }
  try {
    return await ausDatenbank(url, stand);
  } catch (fehler) {
    // Nur die Meldung, nie die Verbindungs-URL (enthält das Passwort).
    const grund = fehler instanceof Error ? fehler.message.replaceAll(url, "<UC3_DATABASE_URL>") : "unbekannt";
    console.warn("[landing] UC3-Datenbank nicht verfügbar, zeige Beispieldaten:", grund);
    return befundeAusFixture(stand);
  }
}
