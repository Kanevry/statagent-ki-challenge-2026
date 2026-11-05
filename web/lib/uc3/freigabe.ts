import { formatZahl, pruefeName } from "@kic/ui/bausteine";
import { literal, type Beleg } from "./beleg";
import { type Ausfuehren, standardAusfuehren, uc3 } from "./cli";
import { lies, type Lesung, type Sql } from "./db";
import { istMonat, monatName } from "./monat";

// Freigaben (UC3): Vorschläge der eigenen Agenten lesen, die Freigabe-Waage aus der Probe bilden und die Entscheidung
// eines Menschen an die CLI weiterreichen (`uc3 freigabe` / `uc3 ablehnen`). Geschrieben wird nur über die CLI;
// sie schreibt meta.freigabe und den Commit mit Trailer „Freigegeben-von“. web/ ruft nie ein Modell.

// ---------------------------------------------------------------------------------------------------------------
// Lesen
// ---------------------------------------------------------------------------------------------------------------

export type VorschlagStatus = "offen" | "freigegeben" | "abgelehnt";

export interface Vorschlag {
  id: number;
  protokollId: number | null;
  erstelltAm: string;
  anweisung: string;
  /** Wer die Anweisung gegeben hat (meta.protokoll, Mensch), sonst null. */
  gesagtVon: string | null;
  gesagtAm: string | null;
  rolle: string;
  typ: string;
  regelsatzZiel: string;
  regelsatzBasis: string;
  aenderungen: unknown[];
  begruendung: string;
  probe: unknown;
  modell: string | null;
  provider: string | null;
  status: VorschlagStatus;
  freigegebenVon: string | null;
  freigegebenAm: string | null;
  commitHash: string | null;
  angewendetAm: string | null;
  anwendenFehler: string | null;
  abgelehntVon: string | null;
  abgelehntAm: string | null;
  ablehnungsgrund: string | null;
}

type Zeile = Record<string, unknown>;

function iso(wert: unknown): string | null {
  if (wert instanceof Date) return wert.toISOString();
  return typeof wert === "string" && wert ? wert : null;
}

function textOderNull(wert: unknown): string | null {
  return typeof wert === "string" && wert.trim() ? wert : null;
}

function vorschlagAus(z: Zeile): Vorschlag {
  const status = String(z.status);
  return {
    id: Number(z.id),
    protokollId: z.protokoll_id == null ? null : Number(z.protokoll_id),
    erstelltAm: iso(z.erstellt_am) ?? "",
    anweisung: String(z.anweisung ?? ""),
    gesagtVon: textOderNull(z.gesagt_von),
    gesagtAm: iso(z.gesagt_am),
    rolle: String(z.rolle ?? ""),
    typ: String(z.typ ?? ""),
    regelsatzZiel: String(z.regelsatz_ziel ?? ""),
    regelsatzBasis: String(z.regelsatz_basis ?? ""),
    aenderungen: Array.isArray(z.aenderungen) ? z.aenderungen : [],
    begruendung: String(z.begruendung ?? ""),
    probe: z.probe ?? {},
    modell: textOderNull(z.modell),
    provider: textOderNull(z.provider),
    status: status === "freigegeben" || status === "abgelehnt" ? status : "offen",
    freigegebenVon: textOderNull(z.freigegeben_von),
    freigegebenAm: iso(z.freigegeben_am),
    commitHash: textOderNull(z.commit_hash),
    angewendetAm: iso(z.angewendet_am),
    anwendenFehler: textOderNull(z.anwenden_fehler),
    abgelehntVon: textOderNull(z.abgelehnt_von),
    abgelehntAm: iso(z.abgelehnt_am),
    ablehnungsgrund: textOderNull(z.ablehnungsgrund),
  };
}

async function tabelleDa(sql: Sql, name: string): Promise<boolean> {
  const [z] = await sql`SELECT to_regclass(${name}) IS NOT NULL AS da`;
  return Boolean(z?.da);
}

/**
 * Wer die Anweisung gesagt hat: die letzte Protokollzeile eines Menschen mit demselben Wortlaut, die vor dem
 * Vorschlag liegt. Ohne meta.protokoll bleibt das Feld leer (die Seite sagt dann „Name nicht erfasst“).
 */
function vorschlagSelect(sql: Sql, mitProtokoll: boolean) {
  return mitProtokoll
    ? sql`
        SELECT v.*, m.name AS gesagt_von, m.zeit AS gesagt_am
        FROM meta.vorschlag v
        LEFT JOIN LATERAL (
          SELECT p.name, p.zeit FROM meta.protokoll p
          WHERE p.uc = 'uc3' AND p.akteur <> 'agent' AND p.anweisung = v.anweisung AND p.zeit <= v.erstellt_am
          ORDER BY p.zeit DESC LIMIT 1
        ) m ON true`
    : sql`SELECT v.*, NULL::text AS gesagt_von, NULL::timestamptz AS gesagt_am FROM meta.vorschlag v`;
}

export interface ErledigtZeile {
  schluessel: string;
  zeit: string;
  art: "freigegeben" | "abgelehnt";
  name: string;
  anweisung: string | null;
  geaendert: string | null;
  begruendung: string | null;
  commit: string | null;
  vorschlag: Vorschlag | null;
  waage: Waage | null;
}

export interface Freigaben {
  offen: Vorschlag[];
  erledigt: ErledigtZeile[];
  bezeichnungen: Bezeichnungen;
}

/** Bezeichnungen der Codes je Merkmal aus stat.klass_* (für die Waage); leer, wenn die Tabellen fehlen. */
export async function ladeBezeichnungen(sql: Sql): Promise<Bezeichnungen> {
  const teile: string[] = [];
  if (await tabelleDa(sql, "stat.klass_qualifikation"))
    teile.push("SELECT 'qualifikation' AS merkmal, code, bezeichnung FROM stat.klass_qualifikation");
  if (await tabelleDa(sql, "stat.klass_beschaeftigungskategorie"))
    teile.push("SELECT 'qualifikation', code, bezeichnung FROM stat.klass_beschaeftigungskategorie");
  if (await tabelleDa(sql, "stat.klass_geschlecht"))
    teile.push("SELECT 'geschlecht', code, bezeichnung FROM stat.klass_geschlecht");
  if (await tabelleDa(sql, "stat.klass_region"))
    teile.push(
      "SELECT 'region', code, bezeichnung FROM (SELECT DISTINCT ON (code) code, bezeichnung FROM stat.klass_region ORDER BY code, gueltig_von DESC) r",
    );
  const ergebnis: Record<string, Record<string, string>> = {};
  if (teile.length === 0) return ergebnis;
  // Feste Texte ohne Eingaben; unsafe nur, weil die Teile zur Laufzeit zusammengesetzt werden.
  const zeilen = await sql.unsafe(teile.join(" UNION ALL "));
  for (const z of zeilen) {
    const merkmal = String(z.merkmal);
    (ergebnis[merkmal] ??= {})[String(z.code)] ??= String(z.bezeichnung);
  }
  return ergebnis;
}

/** Offene und entschiedene Vorschläge, dazu Freigaben aus meta.freigabe und meta.regelstand_freigabe. */
export async function leseFreigaben(): Promise<Lesung<Freigaben>> {
  return lies(async (sql) => {
    const [mitVorschlag, mitProtokoll, mitFreigabe, mitRegelstand] = await Promise.all([
      tabelleDa(sql, "meta.vorschlag"),
      tabelleDa(sql, "meta.protokoll"),
      tabelleDa(sql, "meta.freigabe"),
      tabelleDa(sql, "meta.regelstand_freigabe"),
    ]);
    const bezeichnungen = await ladeBezeichnungen(sql);
    const vorschlaege = mitVorschlag
      ? (await sql`SELECT * FROM (${vorschlagSelect(sql, mitProtokoll)}) x ORDER BY id`).map(vorschlagAus)
      : [];
    const offen = vorschlaege.filter((v) => v.status === "offen");
    const erledigt: ErledigtZeile[] = vorschlaege
      .filter((v) => v.status !== "offen")
      .map((v) => ({
        schluessel: `v${v.id}`,
        zeit: (v.status === "freigegeben" ? v.freigegebenAm : v.abgelehntAm) ?? v.erstelltAm,
        art: v.status === "freigegeben" ? "freigegeben" : "abgelehnt",
        name: (v.status === "freigegeben" ? v.freigegebenVon : v.abgelehntVon) ?? "",
        anweisung: v.anweisung,
        geaendert: aenderungKurz(v),
        begruendung: v.ablehnungsgrund,
        commit: v.commitHash,
        vorschlag: v,
        waage: waage(v.probe, bezeichnungen),
      }));

    const vorschlagProtokolle = new Set(vorschlaege.map((v) => v.protokollId).filter((id) => id !== null));
    if (mitFreigabe && mitProtokoll) {
      const zeilen = await sql`
        SELECT f.id, f.protokoll_id, f.name, f.zeitpunkt, f.entscheidung, f.begruendung, f.objekt_ref,
               p.anweisung, p.wirkung, p.commit_hash
        FROM meta.freigabe f JOIN meta.protokoll p ON p.id = f.protokoll_id
        WHERE p.uc = 'uc3' ORDER BY f.zeitpunkt`;
      for (const z of zeilen) {
        if (vorschlagProtokolle.has(Number(z.protokoll_id))) continue;
        erledigt.push({
          schluessel: `f${String(z.id)}`,
          zeit: iso(z.zeitpunkt) ?? "",
          art: z.entscheidung === "nein" ? "abgelehnt" : "freigegeben",
          name: String(z.name),
          anweisung: textOderNull(z.anweisung),
          geaendert: textOderNull(z.wirkung) ?? textOderNull(z.objekt_ref),
          begruendung: textOderNull(z.begruendung),
          commit: textOderNull(z.commit_hash),
          vorschlag: null,
          waage: null,
        });
      }
    }
    if (mitRegelstand) {
      const zeilen = await sql`
        SELECT regelsatz, lieferung, regelstand, freigegeben_von, freigegeben_am, protokoll_id
        FROM meta.regelstand_freigabe ORDER BY freigegeben_am`;
      for (const z of zeilen) {
        if (z.protokoll_id != null && vorschlagProtokolle.has(Number(z.protokoll_id))) continue;
        const lieferung = String(z.lieferung);
        erledigt.push({
          schluessel: `r${String(z.regelsatz)}-${lieferung}-${String(z.regelstand)}`,
          zeit: iso(z.freigegeben_am) ?? "",
          art: "freigegeben",
          name: String(z.freigegeben_von),
          anweisung: null,
          geaendert: `Regelstand ${String(z.regelstand)} für ${istMonat(lieferung) ? monatName(lieferung) : lieferung}`,
          begruendung: null,
          commit: null,
          vorschlag: null,
          waage: null,
        });
      }
    }
    erledigt.sort((a, b) => b.zeit.localeCompare(a.zeit));
    return { offen, erledigt, bezeichnungen };
  });
}

/** Ein Vorschlag mit Bezeichnungen; `null` in den Daten, wenn es ihn nicht gibt. */
export async function leseVorschlag(
  id: number,
): Promise<Lesung<{ vorschlag: Vorschlag | null; bezeichnungen: Bezeichnungen }>> {
  return lies(async (sql) => {
    if (!(await tabelleDa(sql, "meta.vorschlag"))) return { vorschlag: null, bezeichnungen: {} };
    const mitProtokoll = await tabelleDa(sql, "meta.protokoll");
    const [z] = await sql`SELECT * FROM (${vorschlagSelect(sql, mitProtokoll)}) x WHERE id = ${id}`;
    return { vorschlag: z ? vorschlagAus(z) : null, bezeichnungen: await ladeBezeichnungen(sql) };
  });
}

/** Routen-Parameter → positive ganze Zahl, sonst null (die Seite antwortet dann mit notFound). */
export function vorschlagId(text: string): number | null {
  if (!/^[1-9]\d{0,9}$/.test(text)) return null;
  const id = Number(text);
  return Number.isSafeInteger(id) && id <= 2_147_483_647 ? id : null;
}

// ---------------------------------------------------------------------------------------------------------------
// In Worten
// ---------------------------------------------------------------------------------------------------------------

const ROLLEN: Record<string, string> = {
  datenmanagement: "Datenmanagement-Agent",
  klassifikation: "Klassifikations-Agent",
  qs: "Prüf-Agent",
  reporting: "Berichts-Agent",
};

export function rollenName(rolle: string): string {
  return ROLLEN[rolle] ?? `Agent ${rolle}`;
}

function wert(x: unknown): string {
  if (x === undefined || x === null) return "nichts";
  return typeof x === "string" ? `„${x}“` : JSON.stringify(x);
}

type Aenderung = { regel_name?: unknown; parameter_alt?: unknown; parameter_neu?: unknown; regel?: unknown; pfad?: unknown };

function objekt(x: unknown): Record<string, unknown> {
  return typeof x === "object" && x !== null && !Array.isArray(x) ? (x as Record<string, unknown>) : {};
}

/** Regeländerung in Worten und als Zeilen mit „-“ (fällt weg) und „+“ (kommt dazu); nur geänderte Werte. */
export function klartext(v: Pick<Vorschlag, "typ" | "aenderungen">): { worte: string[]; diff: string } {
  const worte: string[] = [];
  const zeilen: string[] = [];
  for (const roh of v.aenderungen) {
    const a = objekt(roh) as Aenderung;
    if (v.typ === "regel_aendern") {
      const regel = String(a.regel_name ?? "");
      const alt = objekt(a.parameter_alt);
      const neu = objekt(a.parameter_neu);
      for (const k of [...new Set([...Object.keys(alt), ...Object.keys(neu)])].sort()) {
        if (JSON.stringify(alt[k]) === JSON.stringify(neu[k])) continue;
        if (!(k in neu)) worte.push(`In der Regel ${regel} fällt „${k}“ weg.`);
        else if (!(k in alt)) worte.push(`In der Regel ${regel} kommt „${k}“ mit ${wert(neu[k])} dazu.`);
        else worte.push(`In der Regel ${regel} wird „${k}“ von ${wert(alt[k])} auf ${wert(neu[k])} geändert.`);
        if (k in alt) zeilen.push(`- ${regel}: ${k} = ${wert(alt[k])}`);
        if (k in neu) zeilen.push(`+ ${regel}: ${k} = ${wert(neu[k])}`);
      }
    } else if (v.typ === "regel_neu") {
      const r = objekt(a.regel);
      const name = String(r.name ?? "");
      worte.push(typeof r.beschreibung === "string" ? r.beschreibung : `Die Regel ${name} kommt neu dazu.`);
      zeilen.push(`+ ${name}: ${wert(r.parameter)}`);
    } else {
      worte.push("Eine Sonderauswertung kommt dazu. Sie ändert keine Regel und keine Zahl der Statistik.");
      zeilen.push(`+ Datei ${String(a.pfad ?? "")}`);
    }
  }
  return { worte, diff: zeilen.join("\n") };
}

/** Kurzform für das Protokoll: welche Regel oder Datei sich ändert. */
export function aenderungKurz(v: Pick<Vorschlag, "typ" | "aenderungen" | "regelsatzZiel">): string {
  const namen = v.aenderungen.map((roh) => {
    const a = objekt(roh) as Aenderung;
    if (v.typ === "code_datei") return `Datei ${String(a.pfad ?? "")}`;
    return `Regel ${String(a.regel_name ?? objekt(a.regel).name ?? "")}`;
  });
  return v.typ === "code_datei" ? namen.join(", ") : `${namen.join(", ")} (Regelsatz ${v.regelsatzZiel})`;
}

// ---------------------------------------------------------------------------------------------------------------
// Freigabe-Waage aus der Probe
// ---------------------------------------------------------------------------------------------------------------

/** merkmal → code → Bezeichnung */
export type Bezeichnungen = Readonly<Record<string, Readonly<Record<string, string>>>>;

export interface WaageZeile {
  merkmal: string;
  code: string;
  /** „Arbeiter (Qualifikation)“ oder bei der Gesamtzahl „Beschäftigungsverhältnisse gesamt“. */
  bezeichnung: string;
  vorher: number;
  nachher: number;
  differenz: number;
}

export interface Waage {
  lieferung: string;
  /** Die Kategorie mit dem größten Unterschied; nur wenn sich nichts ändert, die Gesamtzahl. */
  haupt: WaageZeile;
  /** Weitere geänderte Kategorien, größter Unterschied zuerst. */
  weitere: WaageZeile[];
  gesamtVorher: number;
  gesamtNachher: number;
}

const MERKMALE: Record<string, string> = { qualifikation: "Qualifikation", geschlecht: "Geschlecht", region: "Region" };

type ProbeZahlen = { gesamt?: unknown; je_merkmal?: unknown };

function zahl(x: unknown): number {
  const n = typeof x === "number" ? x : typeof x === "string" ? Number(x) : Number.NaN;
  return Number.isFinite(n) ? n : 0;
}

/** Probemonate mit Zahlen, neuester zuerst. Akzeptiert `{ "2025-10": {...} }` und einen einzelnen Monat. */
function probeMonate(probe: unknown): { lieferung: string; vorher: ProbeZahlen; nachher: ProbeZahlen }[] {
  const o = objekt(probe);
  const kandidaten = "vorher" in o ? [o] : Object.values(o).map(objekt);
  return kandidaten
    .filter((p) => typeof p.vorher === "object" && p.vorher && typeof p.nachher === "object" && p.nachher)
    .map((p) => ({ lieferung: String(p.lieferung ?? ""), vorher: objekt(p.vorher), nachher: objekt(p.nachher) }))
    .sort((a, b) => b.lieferung.localeCompare(a.lieferung));
}

/**
 * Bildet die Waage: die Kategorie (Merkmal und Code) mit dem größten absoluten Unterschied zwischen vorher und
 * nachher. Eine Gesamtzahl, die gleich bleibt, ist nie die Hauptzeile, solange sich eine Kategorie ändert.
 * Ohne gerechnete Probe: null (keine erfundenen Zahlen).
 */
export function waage(probe: unknown, bezeichnungen: Bezeichnungen = {}): Waage | null {
  const [monat] = probeMonate(probe);
  if (!monat) return null;
  const vm = objekt(monat.vorher.je_merkmal);
  const nm = objekt(monat.nachher.je_merkmal);
  const zeilen: WaageZeile[] = [];
  for (const merkmal of [...new Set([...Object.keys(vm), ...Object.keys(nm)])]) {
    const v = objekt(vm[merkmal]);
    const n = objekt(nm[merkmal]);
    for (const code of [...new Set([...Object.keys(v), ...Object.keys(n)])]) {
      const vorher = zahl(v[code]);
      const nachher = zahl(n[code]);
      if (vorher === nachher) continue;
      const name = bezeichnungen[merkmal]?.[code] ?? code;
      zeilen.push({
        merkmal,
        code,
        bezeichnung: `${name} (${MERKMALE[merkmal] ?? merkmal})`,
        vorher,
        nachher,
        differenz: nachher - vorher,
      });
    }
  }
  zeilen.sort((a, b) => Math.abs(b.differenz) - Math.abs(a.differenz) || a.bezeichnung.localeCompare(b.bezeichnung));
  const gesamtVorher = zahl(monat.vorher.gesamt);
  const gesamtNachher = zahl(monat.nachher.gesamt);
  const gesamt: WaageZeile = {
    merkmal: "gesamt",
    code: "gesamt",
    bezeichnung: "Beschäftigungsverhältnisse gesamt",
    vorher: gesamtVorher,
    nachher: gesamtNachher,
    differenz: gesamtNachher - gesamtVorher,
  };
  const [haupt = gesamt, ...weitere] = zeilen;
  return { lieferung: monat.lieferung, haupt, weitere, gesamtVorher, gesamtNachher };
}

/** Satz zur Waage, etwa „Im Oktober 2025 zählen wir Arbeiter (Qualifikation) 210.000 statt 0.“ */
export function waageSatz(w: Waage): string {
  const monat = istMonat(w.lieferung) ? `Im ${monatName(w.lieferung)} ` : "";
  const { haupt } = w;
  if (haupt.differenz === 0) return `${monat}bleibt ${haupt.bezeichnung} bei ${formatZahl(haupt.vorher)}.`.trim();
  const satz = `${monat}zählen wir ${haupt.bezeichnung} mit ${formatZahl(haupt.nachher)} statt ${formatZahl(haupt.vorher)}.`;
  return satz.charAt(0).toUpperCase() + satz.slice(1);
}

/** Beleg der Waage: die Abfrage auf meta.vorschlag.probe, die genau die Zahlen vorher und nachher liefert. */
export function waageBeleg(vorschlagIdWert: number, w: Waage): Beleg {
  const pfad = (seite: "vorher" | "nachher") =>
    w.haupt.merkmal === "gesamt"
      ? `probe->${literal(w.lieferung)}->'${seite}'->>'gesamt'`
      : `probe->${literal(w.lieferung)}->'${seite}'->'je_merkmal'->${literal(w.haupt.merkmal)}->>${literal(w.haupt.code)}`;
  return {
    quelle: "meta.vorschlag",
    lieferung: w.lieferung || null,
    monat: w.lieferung || null,
    stand: "vorlaeufig",
    verweis: `Probe zu Vorschlag uc3/${vorschlagIdWert}, gerechnet und zurückgerollt`,
    sql: [
      `SELECT coalesce((${pfad("vorher")})::bigint, 0) AS vorher,`,
      `       coalesce((${pfad("nachher")})::bigint, 0) AS nachher`,
      "FROM meta.vorschlag",
      `WHERE id = ${literal(vorschlagIdWert)};`,
    ].join("\n"),
  };
}

// ---------------------------------------------------------------------------------------------------------------
// POST /api/uc3/freigabe
// ---------------------------------------------------------------------------------------------------------------

export const MAX_BODY_BYTES = 4 * 1024;
export const MAX_BEGRUENDUNG = 500;
/** Eine Entscheidung zur Zeit: jede schreibt meta.freigabe und einen Commit im selben Repo. */
export const MAX_ENTSCHEIDUNGEN = 1;

const UNGUELTIG =
  "Die Anfrage braucht JSON mit id (ganze Zahl), name (Vor- und Nachname) und entscheidung (ja oder nein).";

type FehlerStatus = 400 | 403 | 409 | 413 | 429 | 502;

function fehler(status: FehlerStatus, meldung: string, grund?: string): Response {
  return Response.json(grund ? { fehler: meldung, grund } : { fehler: meldung }, {
    status,
    headers: { "cache-control": "no-store" },
  });
}

class ZuGross extends Error {}

async function leseBody(anfrage: Request, grenze: number): Promise<string> {
  const laenge = Number(anfrage.headers.get("content-length") ?? "");
  if (Number.isFinite(laenge) && laenge > grenze) throw new ZuGross();
  if (!anfrage.body) return "";
  const leser = anfrage.body.getReader();
  const stuecke: Uint8Array[] = [];
  let gelesen = 0;
  for (;;) {
    const { done, value } = await leser.read();
    if (done) break;
    gelesen += value.byteLength;
    if (gelesen > grenze) {
      await leser.cancel();
      throw new ZuGross();
    }
    stuecke.push(value);
  }
  return new TextDecoder().decode(Buffer.concat(stuecke));
}

export type Entscheidung =
  | { id: number; name: string; entscheidung: "ja" }
  | { id: number; name: string; entscheidung: "nein"; begruendung: string };

/** Body → Entscheidung oder feste deutsche Meldung. Der Name wird hier noch nicht geprüft (eigene Meldung). */
export function leseEntscheidung(text: string): Entscheidung | { meldung: string } {
  let roh: unknown;
  try {
    roh = JSON.parse(text);
  } catch {
    return { meldung: UNGUELTIG };
  }
  const o = objekt(roh);
  const { id, name, entscheidung, begruendung } = o;
  if (typeof id !== "number" || !Number.isSafeInteger(id) || id < 1 || id > 2_147_483_647) return { meldung: UNGUELTIG };
  if (typeof name !== "string" || (entscheidung !== "ja" && entscheidung !== "nein")) return { meldung: UNGUELTIG };
  if (begruendung !== undefined && typeof begruendung !== "string") return { meldung: UNGUELTIG };
  if (entscheidung === "ja") return { id, name, entscheidung };
  const grund = (begruendung ?? "").trim();
  if (!grund) return { meldung: "Eine Ablehnung braucht eine Begründung." };
  if (grund.length > MAX_BEGRUENDUNG) return { meldung: `Die Begründung ist länger als ${MAX_BEGRUENDUNG} Zeichen.` };
  if (/\p{Cc}/u.test(grund)) return { meldung: "Die Begründung bitte ohne Zeilenumbruch und ohne Steuerzeichen." };
  return { id, name, entscheidung, begruendung: grund };
}

/** argv nach `uc3`; jeder Wert ist ein eigenes Element (execFile, keine Shell). */
export function entscheidungArgv(e: Entscheidung): string[] {
  return e.entscheidung === "ja"
    ? ["freigabe", String(e.id), "--name", e.name, "--json"]
    : ["ablehnen", String(e.id), "--name", e.name, "--begruendung", e.begruendung, "--json"];
}

/**
 * Kurzer Grund aus stderr der CLI: nur der Text nach „nicht freigegeben: “ bzw. „nicht abgelehnt: “, erste Zeile,
 * ohne Dateipfade, höchstens 200 Zeichen. Alles andere (Tracebacks, Umgebung) bleibt auf dem Server.
 */
export function kurzerGrund(stderr: string): string | null {
  const treffer = /nicht (?:freigegeben|abgelehnt): ([^\r\n]*)/.exec(stderr);
  if (!treffer?.[1]) return null;
  const grund = treffer[1]
    .replace(/(?:[A-Za-z]:)?(?:[\\/][\w.@+~-]+){2,}[\\/]?/g, "…")
    .replace(/\s+/g, " ")
    .trim();
  if (!grund) return null;
  return grund.length > 200 ? `${grund.slice(0, 199)}…` : grund;
}

/** Python `str(datetime)` („2026-11-05 14:41:07.655871+01:00“) → ISO, das jeder Browser liest. */
export function isoZeit(wert: unknown): string | null {
  if (typeof wert !== "string" || !wert.trim()) return null;
  const t = /^(\d{4}-\d\d-\d\d)[ T](\d\d:\d\d:\d\d)(\.\d+)?(Z|[+-]\d\d(?::?\d\d)?)?$/.exec(wert.trim());
  if (!t) return null;
  const [, datum, zeit, bruch = "", zone = ""] = t;
  const z = /^[+-]\d\d$/.test(zone) ? `${zone}:00` : zone;
  return `${datum}T${zeit}${bruch.slice(0, 4)}${z}`;
}

export interface FreigabeErfolg {
  zeitpunkt: string | null;
  commit: string | null;
  protokoll_id: number | null;
  /** Nur bei Freigabe: false, wenn die Freigabe gespeichert ist, das Anwenden aber scheiterte. */
  angewendet?: boolean;
}

function erfolgAus(stdout: string, art: "ja" | "nein"): FreigabeErfolg | null {
  let daten: Record<string, unknown>;
  try {
    daten = objekt(JSON.parse(stdout));
  } catch {
    return null;
  }
  const zeitpunkt = isoZeit(art === "ja" ? daten.freigegeben_am : daten.abgelehnt_am);
  if (art === "ja" && (typeof daten.name !== "string" || !zeitpunkt)) return null;
  if (art === "nein" && daten.status !== "abgelehnt") return null;
  const protokoll = Number(daten.protokoll_id);
  return {
    zeitpunkt,
    commit: textOderNull(daten.commit_hash),
    protokoll_id: Number.isSafeInteger(protokoll) && protokoll > 0 ? protokoll : null,
    ...(art === "ja" ? { angewendet: daten.angewendet === true } : {}),
  };
}

export interface FreigabeOptionen {
  ausfuehren?: Ausfuehren;
  umgebung?: Readonly<Record<string, string | undefined>>;
  wurzel?: () => string;
  maxLaeufe?: number;
}

/**
 * Handler für POST /api/uc3/freigabe. Sperren in dieser Reihenfolge, alle vor dem Subprozess:
 * `KIC_ONLINE_LESEND=1` → 403, Body > 4 KiB → 413, ungültige Anfrage → 400, Name ohne Vor- und Nachname → 400,
 * schon eine Entscheidung offen → 429. Danach `uc3 freigabe|ablehnen … --json`: Exit 0 → 200; Exit 1 → 409 mit
 * kurzem Grund, außer bei einer gespeicherten Freigabe, deren Anwenden scheiterte (200, angewendet: false);
 * Timeout oder Startfehler → 502. Name, Begründung und stderr werden nie geloggt.
 */
export function erstelleFreigabeAntwort({
  ausfuehren = standardAusfuehren,
  umgebung = process.env,
  wurzel,
  maxLaeufe = MAX_ENTSCHEIDUNGEN,
}: FreigabeOptionen = {}): (anfrage: Request) => Promise<Response> {
  let offen = 0;

  async function fuehreAus(e: Entscheidung): Promise<Response> {
    let lauf;
    try {
      lauf = await uc3(entscheidungArgv(e), { ausfuehren, ...(wurzel ? { wurzel } : {}) });
    } catch (grund) {
      console.warn(`[uc3/freigabe] CLI nicht erreichbar (${(grund as Error).name ?? "Fehler"})`);
      return fehler(502, "Die Entscheidung konnte nicht gespeichert werden. Bitte gleich noch einmal versuchen.");
    }
    const erfolg = lauf.code === 0 || lauf.code === 1 ? erfolgAus(lauf.stdout, e.entscheidung) : null;
    if (erfolg && (lauf.code === 0 || erfolg.angewendet === false)) {
      return Response.json(erfolg, { headers: { "cache-control": "no-store" } });
    }
    if (lauf.code === 1) {
      const grund = kurzerGrund(lauf.stderr);
      return fehler(409, "Die Entscheidung ist nicht gespeichert.", grund ?? undefined);
    }
    console.warn(`[uc3/freigabe] CLI beendet mit Exit ${lauf.code}`);
    return fehler(502, "Die Entscheidung konnte nicht gespeichert werden. Bitte gleich noch einmal versuchen.");
  }

  return async function freigabeAntwort(anfrage: Request): Promise<Response> {
    if (umgebung.KIC_ONLINE_LESEND === "1") return fehler(403, "In der Online-Demo kann nichts freigegeben werden.");

    let text: string;
    try {
      text = await leseBody(anfrage, MAX_BODY_BYTES);
    } catch (grund) {
      if (grund instanceof ZuGross) return fehler(413, `Die Anfrage ist größer als ${MAX_BODY_BYTES / 1024} KiB.`);
      return fehler(400, UNGUELTIG);
    }
    const eingabe = leseEntscheidung(text);
    if ("meldung" in eingabe) return fehler(400, eingabe.meldung);
    const name = pruefeName(eingabe.name);
    if (!name.gueltig) return fehler(400, name.grund);

    if (offen >= maxLaeufe) return fehler(429, "Gerade wird schon eine Entscheidung gespeichert. Bitte gleich noch einmal.");
    offen += 1;
    try {
      return await fuehreAus({ ...eingabe, name: name.name });
    } finally {
      offen -= 1;
    }
  };
}

/** Prozessweiter Handler für die Route. */
export const freigabeAntwort = erstelleFreigabeAntwort();
