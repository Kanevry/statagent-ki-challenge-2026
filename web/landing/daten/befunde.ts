import postgres from "postgres";
import { ersterSatz, massgeblichCte } from "@/components/uc3/bericht";
import { gruppeAus, gruppeVon, type GruppeArt } from "@/components/uc3/einstufung-gruppen";
import { titelUndMesswerte } from "@/components/uc3/lauf-detail";
import { alltag } from "@/components/uc3/sprache";
import { befundeAusFixture } from "./befunde-fixture";
import { zahl, type Einstufung } from "./fakten";
import type { BefundTabelle, BefundZeile } from "./typen";

/**
 * Tabelle „Gefundene Datenfehler“: lesend aus meta.pruefung_treffer der UC3-Datenbank (UC3_DATABASE_URL), nur die
 * Treffer des maßgeblichen Laufs je Monat im Regelsatz v1. Damit steht hier dasselbe wie auf /uc3/berichte; über alle
 * Läufe gezählt wären es 1.299 Zeilen, und abgebrochene Versuche sähen aus wie angehaltene Monate.
 * Ohne Datenbank, bei Timeout oder ohne Treffer: die 8 Befunde der Gegenrechnung als „Beispieldaten“.
 * Nur serverseitig importieren (postgres.js).
 */

const ZEITLIMIT_MS = 2_500;

/** Verbindung steht, aber die Prüfung hat noch keine Treffer geschrieben: kein Defekt, nur noch kein Lauf. */
class KeineTreffer extends Error {}
const MAX_ZEILEN = 50;

/** Die Startseite zeigt den Stand der Fachbeschreibung; v2 hat seinen eigenen Weg über /uc3?regelsatz=v2. */
const REGELSATZ = "v1";

const CTE = massgeblichCte("$1");
const TREFFER = "FROM massgeblich m\nJOIN meta.pruefung_treffer t ON t.lauf_id = m.quelle_id AND t.anzahl > 0";

// Fester Text aus diesem Modul, der Regelsatz geht als Parameter $1 hinein. Was den Monat anhält zuerst, dann nicht
// Erklärbares, dann die größten; nicht Eingestuftes zuletzt.
const SQL_ZEILEN = [
  CTE,
  "SELECT t.anzahl, t.umfang, t.einstufung, t.anhalten, m.lieferung, r.name, r.beschreibung, r.parameter->>'satz' AS satz",
  TREFFER,
  "LEFT JOIN meta.regel r ON r.id = t.regel_id",
  "ORDER BY t.anhalten DESC NULLS LAST, (t.einstufung = 'nicht-erklaerbar') DESC NULLS LAST,",
  `  (t.einstufung IS NULL), t.anzahl DESC, m.lieferung DESC LIMIT ${MAX_ZEILEN}`,
].join("\n");

const SQL_ANZAHL = [CTE, "SELECT count(*)::text AS anzahl", TREFFER].join("\n");

const CODE: Record<GruppeArt, Einstufung> = {
  fehler: "erklaert-datenproblem",
  "kein-fehler": "erklaert-plausibel",
  offen: "nicht-erklaerbar",
};

interface TrefferRoh {
  anzahl: string | number;
  umfang: string | null;
  einstufung: string | null;
  anhalten: boolean;
  lieferung: string;
  name: string | null;
  beschreibung: string | null;
  satz: string | null;
}

export function zeileAusTreffer(t: TrefferRoh): BefundZeile {
  // Dieselben Wörter wie im Monat und in der Tabelle der Berichte (roter Faden); ohne Einstufung: noch nicht erklärt.
  const art = gruppeAus(t.einstufung);
  const einstufungText = gruppeVon(art).titel;
  const anzahl = Number(t.anzahl);
  // Klartext wie auf der Monatsseite, nie der Rohname der Regel und nie SQL: Belege gehören in den Qualitätsbericht.
  // Nur der erste Satz: Folgesätze der Vorlagen meinen die Monatsseite („steht unten als Revisionsbedarf“).
  const { titel } = titelUndMesswerte(
    { name: t.name ?? "", beschreibung: t.beschreibung ?? "", satz: t.satz, anzahl, umfang: t.umfang },
    t.lieferung,
  );
  return {
    befund: ersterSatz(alltag(titel)) || "Prüfung ohne Beschreibung",
    lieferung: t.lieferung,
    saetze: zahl(anzahl),
    einstufung: CODE[art],
    einstufungText: t.anhalten ? `${einstufungText} · hält den Monat an` : einstufungText,
    anhalten: t.anhalten,
  };
}

async function ausDatenbank(url: string, stand: string): Promise<BefundTabelle> {
  const sql = postgres(url, { max: 1, connect_timeout: 2, idle_timeout: 5, prepare: false, onnotice: () => {} });
  try {
    const abfrage = (async () => {
      const [zeilen, [{ anzahl }]] = await Promise.all([
        sql.unsafe<TrefferRoh[]>(SQL_ZEILEN, [REGELSATZ]),
        sql.unsafe<{ anzahl: string }[]>(SQL_ANZAHL, [REGELSATZ]),
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
