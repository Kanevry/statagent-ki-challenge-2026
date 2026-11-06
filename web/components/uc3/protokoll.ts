import { formatZahl } from "@kic/ui/bausteine";
import { eintragStatus, type Eintrag } from "@kic/ui/shell";
import { lies, type Sql } from "./db";
import { type Bezeichnungen, klarerAenderungsSatz, klartext, ladeBezeichnungen, rollenName } from "./freigabe";
import { mitRegeln, regelsatzName } from "./regelsatz-name";
import { alltag } from "./sprache";

/**
 * Zeile aus meta.protokoll der UC3-Datenbank (Vertrag P). Die optionalen Felder kommen aus meta.vorschlag (über
 * `protokoll_id`) und meta.freigabe (jüngste Entscheidung je `protokoll_id`); sie fehlen, wenn die Tabellen fehlen.
 */
export interface ProtokollZeile {
  id: number | string;
  zeit: Date | string;
  uc: string | null;
  akteur: string;
  name: string | null;
  anweisung: string | null;
  wirkung: string | null;
  status: string;
  modell: string | null;
  provider: string | null;
  ref: string | null;
  rolle?: string | null;
  typ?: string | null;
  aenderungen?: unknown;
  regelsatz_ziel?: string | null;
  freigegeben_von?: string | null;
  freigegeben_am?: Date | string | null;
  abgelehnt_von?: string | null;
  abgelehnt_am?: Date | string | null;
  f_name?: string | null;
  f_zeitpunkt?: Date | string | null;
  f_entscheidung?: string | null;
}

const datumFormat = new Intl.DateTimeFormat("de-AT", {
  timeZone: "Europe/Vienna",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});
const uhrFormat = new Intl.DateTimeFormat("de-AT", {
  timeZone: "Europe/Vienna",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function datum(wert: Date | string | null | undefined): Date | null {
  if (!wert) return null;
  const d = wert instanceof Date ? wert : new Date(wert);
  return Number.isNaN(d.getTime()) ? null : d;
}

function text(wert: string | null | undefined): string | null {
  return typeof wert === "string" && wert.trim() ? wert.trim() : null;
}

/** Wort für einen Regelsatz im Satz: v2 als Stand, die Pensionen-Regeln mit eigenem Namen, sonst `regelsatzName`. */
function regelsatzWort(code: string): string {
  if (code === "v2") return "Stand nach den Änderungsaufträgen";
  if (code.startsWith("pensionen-")) return "Regeln für die Pensionen";
  return regelsatzName(code);
}

/**
 * „Regelsatz v3“ heißt in der App „Neue Fassung 3“, „Regelsatz v2 freigeben“ „Stand nach den Änderungsaufträgen
 * freigeben“, „nach Regelsatz v1“ „nach den alten Regeln“.
 */
function ohneRegelsatzCode(wert: string): string {
  return wert
    .replace(/nach Regelsatz ((?:[a-z]+-)?v[0-9]+)/g, (_ganz: string, code: string) =>
      code.startsWith("pensionen-") ? "nach den Regeln für die Pensionen" : mitRegeln(code),
    )
    .replace(/Regelsatz ((?:[a-z]+-)?v[0-9]+|ministerium)/g, (_ganz: string, code: string) => regelsatzWort(code));
}

// Anweisungen, die das Programm selbst schreibt. Nur sie werden umformuliert.
const PROGRAMM_ANWEISUNG =
  /^(?:Regelsatz [a-z0-9-]+ freigeben|Berichtsmonat [0-9]{4}-[0-9]{2} \(v[0-9]+\) veröffentlichen|Ministeriums-Lieferung [0-9]{4}-[0-9]{2} freigeben(?: .*)?)$/;

/** Der Wortlaut eines Auftrags bleibt wörtlich stehen; nur die festen Sätze des Programms bekommen die Wörter der App. */
function anweisungText(wert: string): string {
  if (!PROGRAMM_ANWEISUNG.test(wert)) return wert;
  const mitNamen = wert.replace(/\((v[0-9]+)\)/, (_ganz: string, code: string) => `(${regelsatzName(code)})`);
  return alltag(ohneRegelsatzCode(mitNamen));
}

/** „Freigegeben von Name, TT.MM.JJJJ, HH:MM“ in Wiener Zeit; ohne Name oder Zeitpunkt null. */
function entscheidungsZeile(z: ProtokollZeile, status: Eintrag["status"]): string | null {
  if (status !== "freigegeben" && status !== "abgelehnt") return null;
  const ausVorschlag =
    status === "freigegeben"
      ? { name: text(z.freigegeben_von), zeit: datum(z.freigegeben_am) }
      : { name: text(z.abgelehnt_von), zeit: datum(z.abgelehnt_am) };
  const passendeFreigabe = (z.f_entscheidung === "nein") === (status === "abgelehnt");
  const ausFreigabe = passendeFreigabe ? { name: text(z.f_name), zeit: datum(z.f_zeitpunkt) } : { name: null, zeit: null };
  const { name, zeit } = ausVorschlag.name && ausVorschlag.zeit ? ausVorschlag : ausFreigabe;
  if (!name || !zeit) return null;
  // Hat derselbe Mensch die Anweisung gegeben und freigegeben, stehen Name und Zeit schon in der Kopfzeile des Eintrags.
  if (z.akteur === "mensch" && name === text(z.name)) return null;
  const wort = status === "freigegeben" ? "Freigegeben" : "Abgelehnt";
  return `${wort} von ${name}, ${datumFormat.format(zeit)}, ${uhrFormat.format(zeit)}`;
}

/** „In der Regel R wird „k“ von „a“ auf „b“ geändert.“ liest sich im Panel leichter als vorher und jetzt. */
function vorherJetzt(satz: string): string {
  return satz.replace(
    /In der Regel ([^ ]+) wird („[^“]+“) von (.+?) auf (.+?) geändert\./g,
    (_ganz: string, regel: string, feld: string, alt: string, neu: string) =>
      `In der Regel ${regel} ändert sich ${feld}: vorher ${alt}, jetzt ${neu}.`,
  );
}

/** Zahlen und Tage in festen Sätzen des Programms: „32741 Personen“ wird „32.741 Personen“, 2025-08-01 wird 01.08.2025. */
function zahlenUndTage(wert: string): string {
  return wert
    .replace(/(?<![0-9.])([0-9]{4,}) Personen/g, (_ganz: string, zahl: string) => `${formatZahl(Number(zahl))} Personen`)
    .replace(/(?<![0-9-])([0-9]{4})-([0-9]{2})-([0-9]{2})(?![0-9-])/g, "$3.$2.$1");
}

/** Wirkung in den Wörtern der App: bei einem Vorschlag ein Satz aus der Änderung, sonst der Text mit Alltagswörtern. */
function wirkungText(z: ProtokollZeile, bezeichnungen: Bezeichnungen): string | null {
  const typ = text(z.typ);
  if (typ) {
    // Je Änderung ein Satz: der klare Satz, sonst die Worte für genau diese Änderung. So fällt bei mehreren Änderungen
    // keine still weg, nur weil eine andere einen klaren Satz hat.
    const saetze = (Array.isArray(z.aenderungen) ? z.aenderungen : []).flatMap((aenderung: unknown) => {
      const einzeln = { typ, aenderungen: [aenderung] };
      const einer = klarerAenderungsSatz(einzeln, bezeichnungen) ?? klartext(einzeln, bezeichnungen).worte.join(" ");
      return einer ? [einer] : [];
    });
    const satz = saetze.join(" ") || null;
    const ziel = text(z.regelsatz_ziel);
    if (satz) {
      const lesbar = vorherJetzt(ohneRegelsatzCode(satz));
      return ziel ? `${regelsatzName(ziel)}: ${lesbar}` : lesbar;
    }
  }
  const roh = text(z.wirkung);
  return roh ? alltag(ohneRegelsatzCode(zahlenUndTage(roh))) : null;
}

/**
 * Bildet eine Zeile auf den JSON-Vertrag `Eintrag` ab; unbekannte Werte fallen auf „offen“ bzw. „agent“. Rohnamen
 * („agent.klassifikation“, „Regelsatz v3“) werden zu Wörtern der App; bei einer Entscheidung steht in `wirkung` eine
 * eigene Zeile mit Name, Datum und Uhrzeit.
 */
export function eintragAus(z: ProtokollZeile, bezeichnungen: Bezeichnungen = {}): Eintrag {
  const status = (eintragStatus as readonly string[]).includes(z.status) ? (z.status as Eintrag["status"]) : "offen";
  const modell = z.modell ? (z.provider ? `${z.modell} (${z.provider})` : z.modell) : null;
  const agent = /^agent\.(.+)$/.exec(z.name ?? "")?.[1];
  const wirkung = [wirkungText(z, bezeichnungen), entscheidungsZeile(z, status)].filter(Boolean).join("\n");
  return {
    id: Number(z.id),
    zeit: (z.zeit instanceof Date ? z.zeit : new Date(z.zeit)).toISOString(),
    uc: "uc3",
    akteur: z.akteur === "mensch" ? "mensch" : "agent",
    name: agent ? rollenName(agent) : (z.name ?? ""),
    anweisung: anweisungText(z.anweisung ?? ""),
    wirkung: wirkung || null,
    status,
    modell,
    ref: z.ref,
  };
}

async function tabelleDa(sql: Sql, name: string): Promise<boolean> {
  const [z] = await sql`SELECT to_regclass(${name}) IS NOT NULL AS da`;
  return Boolean(z?.da);
}

export async function ladeProtokoll(sql: Sql, grenze = 200): Promise<Eintrag[]> {
  const [mitVorschlag, mitFreigabe] = await Promise.all([tabelleDa(sql, "meta.vorschlag"), tabelleDa(sql, "meta.freigabe")]);
  // Fehlt eine Tabelle, liefert der Teil nur leere Spalten; die Seite scheitert nie an einer fehlenden Tabelle.
  const vorschlag = mitVorschlag
    ? sql`LEFT JOIN LATERAL (
        SELECT v.rolle, v.typ, v.aenderungen, v.regelsatz_ziel,
               v.freigegeben_von, v.freigegeben_am, v.abgelehnt_von, v.abgelehnt_am
        FROM meta.vorschlag v WHERE v.protokoll_id = p.id ORDER BY v.id DESC LIMIT 1
      ) v ON true`
    : sql`LEFT JOIN LATERAL (
        SELECT NULL::text AS rolle, NULL::text AS typ, NULL::jsonb AS aenderungen, NULL::text AS regelsatz_ziel,
               NULL::text AS freigegeben_von, NULL::timestamptz AS freigegeben_am,
               NULL::text AS abgelehnt_von, NULL::timestamptz AS abgelehnt_am
      ) v ON true`;
  const freigabe = mitFreigabe
    ? sql`LEFT JOIN LATERAL (
        SELECT f.name AS f_name, f.zeitpunkt AS f_zeitpunkt, f.entscheidung::text AS f_entscheidung
        FROM meta.freigabe f WHERE f.protokoll_id = p.id ORDER BY f.zeitpunkt DESC, f.id DESC LIMIT 1
      ) f ON true`
    : sql`LEFT JOIN LATERAL (
        SELECT NULL::text AS f_name, NULL::timestamptz AS f_zeitpunkt, NULL::text AS f_entscheidung
      ) f ON true`;
  const zeilen = await sql<ProtokollZeile[]>`
    SELECT p.id, p.zeit, p.uc, p.akteur, p.name, p.anweisung, p.wirkung, p.status, p.modell, p.provider, p.ref,
           v.rolle, v.typ, v.aenderungen, v.regelsatz_ziel,
           v.freigegeben_von, v.freigegeben_am, v.abgelehnt_von, v.abgelehnt_am,
           f.f_name, f.f_zeitpunkt, f.f_entscheidung
    FROM meta.protokoll p
    ${vorschlag}
    ${freigabe}
    WHERE p.uc IS NULL OR p.uc = 'uc3'
    ORDER BY p.id DESC
    LIMIT ${grenze}`;
  const bezeichnungen = mitVorschlag ? await ladeBezeichnungen(sql) : {};
  return zeilen.map((z) => eintragAus(z, bezeichnungen));
}

/** Quelle für `protokollAntwort`: ohne Datenbank eine leere Liste (die Schublade zeigt dann ihren Leerzustand). */
export async function protokollQuelle(): Promise<Eintrag[]> {
  const lesung = await lies((sql) => ladeProtokoll(sql));
  return lesung.ok ? lesung.daten : [];
}
