import { formatZahl, pruefeName } from "@kic/ui/bausteine";
import { literal, type Beleg } from "./beleg";
import { type Ausfuehren, standardAusfuehren, uc3 } from "./cli";
import { lies, type Lesung, type Sql } from "./db";
import { ladeMassgeblichenLauf } from "./laeufe";
import { istMonat, monatName, monatsgrenzen } from "./monat";
import type { Lauf } from "./typen";
import { alltag } from "./sprache";

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
  /** Nur bei Einträgen aus meta.regelstand_freigabe: Regelsatz und Monat, für die der Regelstand gilt. */
  regelstand?: { regelsatz: string; lieferung: string } | null;
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
          regelstand: { regelsatz: String(z.regelsatz), lieferung },
        });
      }
    }
    erledigt.sort((a, b) => b.zeit.localeCompare(a.zeit));
    return { offen, erledigt, bezeichnungen };
  });
}

/** Wohin „Ergebnis ansehen“ führt: Monat, Regelsatz und ob es dafür schon einen fertigen Lauf gibt. */
export interface ErgebnisZiel {
  monat: string;
  regelsatz: string;
  /** false: für Monat und Regelsatz gibt es in meta.lauf noch keinen fertigen Lauf. */
  laufDa: boolean;
}

/** Abfrage hinter `laufDa`: fertige Läufe eines Monats mit einem Regelsatz (für den Beleg-Chip). */
export function sqlErgebnisLauf(monat: string, regelsatz: string): string {
  return [
    "SELECT count(*) AS laeufe",
    "FROM meta.lauf",
    `WHERE lieferung = ${literal(monat)} AND regelsatz = ${literal(regelsatz)} AND status IN ('fertig', 'unveraendert');`,
  ].join("\n");
}

/** Pfad der Lauf-Detailseite mit Regelsatz, etwa /uc3/laeufe/2025-10?regelsatz=v2. */
export function ergebnisPfad(z: Pick<ErgebnisZiel, "monat" | "regelsatz">): string {
  return `/uc3/laeufe/${z.monat}?regelsatz=${encodeURIComponent(z.regelsatz)}`;
}

/**
 * Ziel des Ergebnis-Links: nach einer Freigabe der Regelsatz des Vorschlags (regelsatz_ziel), nach einer Ablehnung
 * der bisherige (regelsatz_basis). Monat ist der Monat der Probe, sonst der neueste Monat mit fertigem Lauf in einem
 * der beiden Regelsätze. Ohne meta.lauf oder ohne Monat: null.
 */
async function ladeErgebnisZiel(sql: Sql, v: Vorschlag): Promise<ErgebnisZiel | null> {
  if (v.status === "offen" || !(await tabelleDa(sql, "meta.lauf"))) return null;
  const regelsatz = v.status === "freigegeben" ? v.regelsatzZiel : v.regelsatzBasis;
  if (!regelsatz) return null;
  let monat = probeMonate(v.probe).find((m) => istMonat(m.lieferung))?.lieferung ?? null;
  if (!monat) {
    const [z] = await sql`
      SELECT max(lieferung) AS monat FROM meta.lauf
      WHERE regelsatz IN (${v.regelsatzZiel}, ${v.regelsatzBasis}) AND status IN ('fertig', 'unveraendert')`;
    monat = typeof z?.monat === "string" && istMonat(z.monat) ? z.monat : null;
  }
  if (!monat) return null;
  const [l] = await sql`
    SELECT count(*)::int AS laeufe FROM meta.lauf
    WHERE lieferung = ${monat} AND regelsatz = ${regelsatz} AND status IN ('fertig', 'unveraendert')`;
  return { monat, regelsatz, laufDa: Number(l?.laeufe ?? 0) > 0 };
}

/** Ein Vorschlag mit Bezeichnungen und Ergebnis-Ziel; `null` in den Daten, wenn es ihn nicht gibt. */
export async function leseVorschlag(id: number): Promise<
  Lesung<{
    vorschlag: Vorschlag | null;
    bezeichnungen: Bezeichnungen;
    kategorien: Kategorien;
    ergebnis: ErgebnisZiel | null;
    wirkung: EchteWirkung | null;
  }>
> {
  return lies(async (sql) => {
    if (!(await tabelleDa(sql, "meta.vorschlag")))
      return { vorschlag: null, bezeichnungen: {}, kategorien: {}, ergebnis: null, wirkung: null };
    const mitProtokoll = await tabelleDa(sql, "meta.protokoll");
    const [z] = await sql`SELECT * FROM (${vorschlagSelect(sql, mitProtokoll)}) x WHERE id = ${id}`;
    const vorschlag = z ? vorschlagAus(z) : null;
    return {
      vorschlag,
      bezeichnungen: await ladeBezeichnungen(sql),
      kategorien: await ladeKategorien(sql),
      ergebnis: vorschlag ? await ladeErgebnisZiel(sql, vorschlag) : null,
      wirkung: vorschlag ? await ladeEchteWirkung(sql, vorschlag) : null,
    };
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
  /**
   * Hauptzeile: die Kategorie mit dem größten Unterschied. Bei einer Umschlüsselung (Gesamtzahl gleich, Kategorien
   * verschieben sich) und wenn sich nichts ändert die Gesamtzahl.
   */
  haupt: WaageZeile;
  /** Weitere geänderte Kategorien, größter Unterschied zuerst; bei einer Umschlüsselung alle verschobenen. */
  weitere: WaageZeile[];
  /** Die Gesamtzahl vorher und nachher. */
  gesamt: WaageZeile;
  /** true: dieselben Verhältnisse verteilen sich auf andere Kategorien, die Gesamtzahl bleibt. */
  umverteilung: boolean;
  gesamtVorher: number;
  gesamtNachher: number;
}

const MERKMALE: Record<string, string> = { qualifikation: "Qualifikation", geschlecht: "Geschlecht", region: "Region" };

type ProbeZahlen = { gesamt?: unknown; je_merkmal?: unknown };

function zahl(x: unknown): number {
  const n = typeof x === "number" ? x : typeof x === "string" ? Number(x) : Number.NaN;
  return Number.isFinite(n) ? n : 0;
}

/**
 * Probemonate mit Zahlen, neuester zuerst. Akzeptiert `{ "2025-10": {...} }` und einen einzelnen Monat. Der Monat ist
 * der Schlüssel im jsonb (so schreibt ihn die CLI); nur ohne Monatsschlüssel gilt das Feld `lieferung`.
 */
function probeMonate(probe: unknown): { lieferung: string; vorher: ProbeZahlen; nachher: ProbeZahlen }[] {
  const o = objekt(probe);
  const kandidaten: [string, Record<string, unknown>][] =
    "vorher" in o ? [["", o]] : Object.entries(o).map(([k, p]) => [k, objekt(p)]);
  return kandidaten
    .filter(([, p]) => typeof p.vorher === "object" && p.vorher && typeof p.nachher === "object" && p.nachher)
    .map(([schluessel, p]) => ({
      lieferung: istMonat(schluessel) ? schluessel : String(p.lieferung ?? ""),
      vorher: objekt(p.vorher),
      nachher: objekt(p.nachher),
    }))
    .sort((a, b) => b.lieferung.localeCompare(a.lieferung));
}

/** „Probe für August 2024“ aus dem Monat der Probe; ohne erkennbaren Monat „Probe“. */
export function probeTitel(lieferung: string): string {
  return istMonat(lieferung) ? `Probe für ${monatName(lieferung)}` : "Probe";
}

/**
 * Bildet die Waage. Ändert sich die Gesamtzahl, ist die Hauptzeile die Kategorie (Merkmal und Code) mit dem größten
 * absoluten Unterschied, und `gesamt` trägt die Änderung der Gesamtzahl. Bleibt die Gesamtzahl gleich, während sich
 * Kategorien ändern, ist das eine Umschlüsselung: Hauptzeile ist die Gesamtzahl, alle verschobenen Kategorien stehen
 * unter `weitere`. Sonst stünde „Arbeiter 0 → 210.000“ groß da und läse sich wie 210.000 zusätzliche Verhältnisse.
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
  const gesamtBekannt = monat.vorher.gesamt !== undefined && monat.nachher.gesamt !== undefined && gesamtVorher > 0;
  const umverteilung = zeilen.length > 0 && gesamtBekannt && gesamtVorher === gesamtNachher;
  if (umverteilung) {
    return { lieferung: monat.lieferung, haupt: gesamt, weitere: zeilen, gesamt, umverteilung, gesamtVorher, gesamtNachher };
  }
  const [haupt = gesamt, ...weitere] = zeilen;
  return { lieferung: monat.lieferung, haupt, weitere, gesamt, umverteilung, gesamtVorher, gesamtNachher };
}

/**
 * Eine Zeile zur Gesamtzahl, wenn sie sich ändert und nicht schon die Hauptzeile ist, etwa
 * „Gesamt: 410.587 → 412.000 (+1.413)“. Sonst null.
 */
export function gesamtZeile(w: Waage): WaageZeile | null {
  return w.haupt.merkmal !== "gesamt" && w.gesamt.differenz !== 0 ? w.gesamt : null;
}

/** Satz zur Waage, etwa „Im Oktober 2025 zählen wir Arbeiter (Qualifikation) 210.000 statt 0.“ */
export function waageSatz(w: Waage): string {
  const monat = istMonat(w.lieferung) ? `Im ${monatName(w.lieferung)} ` : "";
  const { haupt } = w;
  if (w.umverteilung) {
    const zahl = formatZahl(w.gesamtVorher);
    return monat
      ? `${monat}verteilen sich die ${zahl} Beschäftigungsverhältnisse neu, gesamt bleibt ${zahl}.`
      : `Die ${zahl} Beschäftigungsverhältnisse verteilen sich neu, gesamt bleibt ${zahl}.`;
  }
  if (haupt.differenz === 0) return `${monat}bleibt ${haupt.bezeichnung} bei ${formatZahl(haupt.vorher)}.`.trim();
  const satz = `${monat}zählen wir ${haupt.bezeichnung} mit ${formatZahl(haupt.nachher)} statt ${formatZahl(haupt.vorher)}.`;
  return satz.charAt(0).toUpperCase() + satz.slice(1);
}

/**
 * Beleg einer Zeile der Waage (Standard: Hauptzeile): die Abfrage auf meta.vorschlag.probe, die genau die Zahlen
 * vorher und nachher dieser Zeile liefert.
 */
export function waageBeleg(vorschlagIdWert: number, w: Waage, zeile: WaageZeile = w.haupt): Beleg {
  const pfad = (seite: "vorher" | "nachher") =>
    zeile.merkmal === "gesamt"
      ? `probe->${literal(w.lieferung)}->'${seite}'->>'gesamt'`
      : `probe->${literal(w.lieferung)}->'${seite}'->'je_merkmal'->${literal(zeile.merkmal)}->>${literal(zeile.code)}`;
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
// Umverteilung der Qualifikationen in Worten (Probe) und echte Wirkung aus den Läufen
// ---------------------------------------------------------------------------------------------------------------

/** Qualifikationscode → Beschäftigungskategorie und ob es ein freier Dienstvertrag ist (stat.klass_qualifikation). */
export type Kategorien = Readonly<Record<string, { kategorie: string; frei: boolean | null }>>;

export const SQL_KATEGORIEN = [
  "SELECT code, beschaeftigungskategorie, freier_dienstvertrag",
  "FROM stat.klass_qualifikation ORDER BY code;",
].join("\n");

export async function ladeKategorien(sql: Sql): Promise<Kategorien> {
  if (!(await tabelleDa(sql, "stat.klass_qualifikation"))) return {};
  const zeilen = await sql`SELECT code, beschaeftigungskategorie, freier_dienstvertrag FROM stat.klass_qualifikation`;
  const ergebnis: Record<string, { kategorie: string; frei: boolean | null }> = {};
  for (const z of zeilen) {
    ergebnis[String(z.code)] = {
      kategorie: String(z.beschaeftigungskategorie),
      frei: typeof z.freier_dienstvertrag === "boolean" ? z.freier_dienstvertrag : null,
    };
  }
  return ergebnis;
}

export interface UmverteilungTeil {
  code: string;
  wert: number;
  frei: boolean | null;
}

export interface UmverteilungGruppe {
  /** Neue Kategorie, etwa „Arbeiter“. */
  ziel: string;
  nachher: number;
  /** Bisherige Qualifikationen, die genau diese Kategorie ergeben. */
  teile: UmverteilungTeil[];
}

export interface Umverteilung {
  lieferung: string;
  gruppen: UmverteilungGruppe[];
  /** Kategorien, die vorher und nachher gleich heißen und gleich viele zählen (etwa Beamte). */
  bleibt: { code: string; wert: number }[];
  gesamt: number;
}

/**
 * Liest aus der Probe, wie sich die Qualifikationen zu Kategorien zusammenfügen: Jede neue Kategorie muss genau die
 * Summe der bisherigen Codes dieser Kategorie (laut stat.klass_qualifikation) sein, jeder weggefallene Code muss in
 * einer neuen Kategorie aufgehen und die Gesamtzahl muss gleich bleiben. Sonst null, dann zeigt die Seite die Waage.
 */
export function umverteilung(probe: unknown, kategorien: Kategorien): Umverteilung | null {
  const [monat] = probeMonate(probe);
  if (!monat) return null;
  const gesamtVorher = zahl(monat.vorher.gesamt);
  if (gesamtVorher <= 0 || gesamtVorher !== zahl(monat.nachher.gesamt)) return null;
  const v = objekt(objekt(monat.vorher.je_merkmal).qualifikation);
  const n = objekt(objekt(monat.nachher.je_merkmal).qualifikation);
  const neu = Object.keys(n).filter((c) => !(c in v));
  const weg = Object.keys(v).filter((c) => !(c in n));
  if (neu.length === 0 || weg.length === 0) return null;
  const gruppen: UmverteilungGruppe[] = [];
  const verbraucht = new Set<string>();
  for (const ziel of neu) {
    const teile = weg
      .filter((c) => kategorien[c]?.kategorie === ziel)
      .map((c) => ({ code: c, wert: zahl(v[c]), frei: kategorien[c]?.frei ?? null }))
      .sort((a, b) => Number(a.frei) - Number(b.frei) || a.code.localeCompare(b.code));
    const nachher = zahl(n[ziel]);
    if (teile.length === 0 || teile.reduce((s, t) => s + t.wert, 0) !== nachher) return null;
    for (const t of teile) verbraucht.add(t.code);
    gruppen.push({ ziel, nachher, teile });
  }
  if (weg.some((c) => !verbraucht.has(c))) return null;
  gruppen.sort((a, b) => b.nachher - a.nachher);
  const bleibt = Object.keys(n)
    .filter((c) => c in v && zahl(v[c]) === zahl(n[c]))
    .map((c) => ({ code: c, wert: zahl(n[c]) }));
  return { lieferung: monat.lieferung, gruppen, bleibt, gesamt: gesamtVorher };
}

/** „141.331 mit Dienstvertrag“ oder „382 freie Dienstverträge“; ohne Angabe zum Vertrag die Bezeichnung. */
export function teilWort(t: UmverteilungTeil, bezeichnung?: string): string {
  if (t.frei === false) return `${formatZahl(t.wert)} mit Dienstvertrag`;
  if (t.frei === true) return `${formatZahl(t.wert)} ${t.wert === 1 ? "freier Dienstvertrag" : "freie Dienstverträge"}`;
  return `${formatZahl(t.wert)} ${bezeichnung ?? t.code}`;
}

/** „Arbeiter 141.713 = 141.331 mit Dienstvertrag + 382 freie Dienstverträge“ */
export function gruppenSatz(g: UmverteilungGruppe, bezeichnungen: Bezeichnungen = {}): string {
  const teile = g.teile.map((t) => teilWort(t, bezeichnungen.qualifikation?.[t.code]));
  return `${g.ziel} ${formatZahl(g.nachher)} = ${teile.join(" + ")}`;
}

/** Beleg einer Gruppe: die neue Kategorie nachher und jeder bisherige Code vorher, alles aus der Probe. */
export function gruppenBeleg(vorschlagIdWert: number, u: Umverteilung, g: UmverteilungGruppe): Beleg {
  const feld = (seite: "vorher" | "nachher", code: string) =>
    `(probe->${literal(u.lieferung)}->'${seite}'->'je_merkmal'->'qualifikation'->>${literal(code)})::bigint`;
  const spalten = [
    `${feld("nachher", g.ziel)} AS ${spaltenName(`${g.ziel}_nachher`)}`,
    ...g.teile.map((t) => `${feld("vorher", t.code)} AS ${spaltenName(`${t.code}_vorher`)}`),
  ];
  return {
    quelle: "meta.vorschlag",
    lieferung: u.lieferung,
    monat: u.lieferung,
    stand: "vorlaeufig",
    verweis: `Probe zu Vorschlag uc3/${vorschlagIdWert}, gerechnet und zurückgerollt`,
    sql: [`SELECT ${spalten.join(",\n       ")}`, "FROM meta.vorschlag", `WHERE id = ${literal(vorschlagIdWert)};`].join("\n"),
  };
}

function spaltenName(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9_]/g, "_");
}

/** Ein Regelsatz im jüngsten Monat, für den es mit beiden Regelsätzen einen fertigen Lauf gibt. */
export interface WirkungSeite {
  lauf: Lauf;
  /** Verhältnisse je gezähltem Qualifikationscode des Laufs. */
  je: Record<string, number>;
  gesamt: number;
}

export interface EchteWirkung {
  monat: string;
  basis: WirkungSeite;
  ziel: WirkungSeite;
  /** Weitere freigegebene Aufträge mit demselben Ziel-Regelsatz (deren Wirkung steckt mit in `ziel`). */
  auchImZiel: string[];
}

/** Titel eines Auftrags: der Teil der Anweisung vor dem ersten Doppelpunkt, etwa „Auftrag 2, ganzes Monat statt Stichtag“. */
export function auftragTitel(anweisung: string): string {
  const [kopf = ""] = anweisung.split(":");
  return kopf.trim().length > 0 && kopf.length <= 120 ? kopf.trim() : anweisung.slice(0, 80).trim();
}

/**
 * SQL hinter den Zahlen eines Laufs: Verhältnisse je Beschäftigungskategorie und je gezähltem Code, mit Gesamtsumme
 * (Zeile ohne Kategorie). Gezählte Codes, die selbst eine Kategorie sind (Regelsatz v2), stehen unter sich selbst.
 */
export function sqlWirkung(lauf: Pick<Lauf, "lieferung" | "regelsatz" | "regelstand">): string {
  const { von, bis } = monatsgrenzen(lauf.lieferung);
  return [
    "SELECT coalesce(k.beschaeftigungskategorie, s.qualifikation) AS kategorie, s.qualifikation,",
    "       sum(s.wert) AS beschaeftigungsverhaeltnisse",
    "FROM stat.stat_beschaeftigte s",
    "LEFT JOIN stat.klass_qualifikation k ON k.code = s.qualifikation",
    `WHERE s.regelsatz = ${literal(lauf.regelsatz)} AND s.regelstand = ${literal(lauf.regelstand)}`,
    "  AND s.variable = 'Beschaeftigungsverhaeltnisse'",
    `  AND s.zeitraum_bis BETWEEN ${literal(von)} AND ${literal(bis)}`,
    "GROUP BY ROLLUP (1, 2) ORDER BY 1, 2;",
  ].join("\n");
}

/** SQL, das den Vergleichsmonat bestimmt: der jüngste Monat mit fertigem Lauf in beiden Regelsätzen. */
export function sqlWirkungMonat(basis: string, ziel: string): string {
  return [
    "SELECT max(a.lieferung) AS monat FROM meta.lauf a",
    `WHERE a.regelsatz = ${literal(basis)} AND a.status IN ('fertig', 'unveraendert')`,
    "  AND EXISTS (SELECT 1 FROM meta.lauf b",
    `              WHERE b.regelsatz = ${literal(ziel)} AND b.lieferung = a.lieferung`,
    "                AND b.status IN ('fertig', 'unveraendert'));",
  ].join("\n");
}

async function ladeSeite(sql: Sql, monat: string, regelsatz: string): Promise<WirkungSeite | null> {
  const lauf = await ladeMassgeblichenLauf(sql, monat, regelsatz);
  if (!lauf) return null;
  const { von, bis } = monatsgrenzen(monat);
  const zeilen = await sql`
    SELECT qualifikation, sum(wert)::bigint AS wert FROM stat.stat_beschaeftigte
    WHERE regelsatz = ${lauf.regelsatz} AND regelstand = ${lauf.regelstand}
      AND variable = 'Beschaeftigungsverhaeltnisse' AND zeitraum_bis BETWEEN ${von} AND ${bis}
    GROUP BY qualifikation`;
  if (zeilen.length === 0) return null;
  const je: Record<string, number> = {};
  for (const z of zeilen) je[String(z.qualifikation)] = zahl(z.wert);
  return { lauf, je, gesamt: Object.values(je).reduce((s, x) => s + x, 0) };
}

/**
 * Echte Wirkung eines freigegebenen Regel-Vorschlags: Zahlen des jüngsten Monats, den beide Regelsätze schon
 * gerechnet haben. Ohne solchen Monat null (dann zeigt die Seite nur die Probe, nichts Erfundenes).
 */
async function ladeEchteWirkung(sql: Sql, v: Vorschlag): Promise<EchteWirkung | null> {
  if (v.status !== "freigegeben" || v.typ === "code_datei" || !v.regelsatzBasis || v.regelsatzBasis === v.regelsatzZiel)
    return null;
  if (!(await tabelleDa(sql, "meta.lauf")) || !(await tabelleDa(sql, "stat.stat_beschaeftigte"))) return null;
  const [m] = await sql`
    SELECT max(a.lieferung) AS monat FROM meta.lauf a
    WHERE a.regelsatz = ${v.regelsatzBasis} AND a.status IN ('fertig', 'unveraendert')
      AND EXISTS (SELECT 1 FROM meta.lauf b WHERE b.regelsatz = ${v.regelsatzZiel} AND b.lieferung = a.lieferung
                    AND b.status IN ('fertig', 'unveraendert'))`;
  const monat = typeof m?.monat === "string" && istMonat(m.monat) ? m.monat : null;
  if (!monat) return null;
  const [basis, ziel] = await Promise.all([ladeSeite(sql, monat, v.regelsatzBasis), ladeSeite(sql, monat, v.regelsatzZiel)]);
  if (!basis || !ziel) return null;
  const andere = await sql`
    SELECT anweisung FROM meta.vorschlag
    WHERE regelsatz_ziel = ${v.regelsatzZiel} AND status = 'freigegeben' AND id <> ${v.id} AND typ <> 'code_datei'
    ORDER BY id`;
  return { monat, basis, ziel, auchImZiel: andere.map((z) => auftragTitel(String(z.anweisung ?? ""))) };
}

/** Eine Kategorie im Vergleich der Läufe: Summe der Codes dieser Kategorie in beiden Regelsätzen. */
export interface WirkungKategorie {
  kategorie: string;
  basis: number;
  ziel: number;
  /** Gezählte Codes im Basis-Lauf, wenn er die Kategorie in mehreren Codes führt. */
  basisTeile: UmverteilungTeil[];
}

/** Fasst beide Läufe je Beschäftigungskategorie zusammen, größte Kategorie zuerst; „Unbekannt“ ohne Zahl fällt weg. */
export function wirkungJeKategorie(w: EchteWirkung, kategorien: Kategorien): WirkungKategorie[] {
  const kat = (code: string) => kategorien[code]?.kategorie ?? code;
  const ergebnis = new Map<string, WirkungKategorie>();
  const eintrag = (k: string) =>
    ergebnis.get(k) ?? ergebnis.set(k, { kategorie: k, basis: 0, ziel: 0, basisTeile: [] }).get(k)!;
  for (const [code, wert] of Object.entries(w.basis.je)) {
    const e = eintrag(kat(code));
    e.basis += wert;
    if (code !== e.kategorie) e.basisTeile.push({ code, wert, frei: kategorien[code]?.frei ?? null });
  }
  for (const [code, wert] of Object.entries(w.ziel.je)) eintrag(kat(code)).ziel += wert;
  for (const e of ergebnis.values()) e.basisTeile.sort((a, b) => Number(a.frei) - Number(b.frei) || a.code.localeCompare(b.code));
  return [...ergebnis.values()].filter((e) => e.basis > 0 || e.ziel > 0).sort((a, b) => b.basis - a.basis);
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
 * Fester Satz für jeden Fehler, den die CLI nicht als bekannten fachlichen Fehler meldet (auch Git-Fehler). Die
 * Freigabe-Karte (@kic/ui) setzt selbst „Nicht gespeichert.“ davor, deshalb sagt der Satz das nicht noch einmal
 * (Abnahme 135-12).
 */
export const GRUND_UNBEKANNT = "Bitte später noch einmal versuchen.";
/** Satz, wenn die CLI nicht startet oder unerwartet endet; die Karte setzt „Nicht gespeichert.“ davor. */
export const DIENST_NICHT_ERREICHBAR = "Der Dienst antwortet gerade nicht. Bitte gleich noch einmal versuchen.";

/**
 * Bekannte fachliche Fehler der CLI (stderr „nicht freigegeben: …“ bzw. „nicht abgelehnt: …“) → fester Satz.
 * Die Muster folgen den Meldungen von plattform.freigabe (NameUngueltig, VorschlagUngueltig) und
 * statagent.agenten (VorschlagFehler). Text aus stderr erreicht den Client nie (SEC-009): Git-Fehler (GitFehler
 * mit git-stderr), Tracebacks und alles Unbekannte ergeben GRUND_UNBEKANNT.
 */
const BEKANNTE_FEHLER: readonly [RegExp, string][] = [
  [
    /^(?:Name enthält Steuerzeichen|Name darf keinen Doppelpunkt|Vor- und Nachname nötig|kein Namensbestandteil|Rollenbezeichnung statt Name|Wörter wiederholen sich|nur Initialen)/,
    "Bitte Vor- und Nachname eingeben.",
  ],
  [/^Vorschlag (?:uc3\/)?\d+ (?:ist bereits |ist \w+, nicht offen)/, "Über diese Änderung ist schon entschieden."],
  [/^Vorschlag (?:uc3\/)?\d+ (?:gibt es nicht|existiert nicht)/, "Diesen Vorschlag gibt es nicht."],
  [/^(?:Eine )?Ablehnung braucht eine Begründung/, "Eine Ablehnung braucht eine Begründung."],
];

export function kurzerGrund(stderr: string): string {
  const treffer = /^nicht (?:freigegeben|abgelehnt): ([^\r\n]*)/m.exec(stderr);
  const meldung = treffer?.[1]?.trim() ?? "";
  for (const [muster, satz] of BEKANNTE_FEHLER) if (muster.test(meldung)) return satz;
  return GRUND_UNBEKANNT;
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
 * festem Satz je bekanntem Fehler (nie stderr), außer bei einer gespeicherten Freigabe, deren Anwenden scheiterte (200, angewendet: false);
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
      return fehler(502, DIENST_NICHT_ERREICHBAR);
    }
    const erfolg = lauf.code === 0 || lauf.code === 1 ? erfolgAus(lauf.stdout, e.entscheidung) : null;
    if (erfolg && (lauf.code === 0 || erfolg.angewendet === false)) {
      return Response.json(erfolg, { headers: { "cache-control": "no-store" } });
    }
    if (lauf.code === 1) {
      const grund = kurzerGrund(lauf.stderr);
      const meldung =
        grund === GRUND_UNBEKANNT ? GRUND_UNBEKANNT : "Die Angaben passen nicht.";
      return fehler(409, meldung, grund);
    }
    console.warn(`[uc3/freigabe] CLI beendet mit Exit ${lauf.code}`);
    return fehler(502, DIENST_NICHT_ERREICHBAR);
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

/** Sätze, mit denen eine Anweisung den Agenten selbst anspricht („Ändere dafür nur …“, „Ziel ist …“). */
const AN_DEN_AGENTEN = /^(Ändere|Ändern|Setze|Lege|Nutze|Verwende|Schreibe|Erzeuge|Baue|Ziel ist)\b/;

/**
 * Der fachliche Auftrag als Zitat für die Freigabe: ohne Titel vor dem Doppelpunkt, ohne Klammern mit Dateien oder
 * Spaltennamen und ohne die Sätze an den Agenten (Sichtprüfung bb, #18). Bleibt nichts übrig, steht der Rohtext da.
 */
export function auftragsZitat(anweisung: string): string {
  // Nur ein erkannter Titel „Auftrag N, …:“ fällt weg; jeder andere Doppelpunkt gehört zum Auftrag (Review !77).
  const rumpf = anweisung
    .replace(/^\s*Auftrag \d+[^:]{0,80}:/, "")
    .replace(/\s*\([^)]*(?:\.csv|Spalte|[A-Z]{4,})[^)]*\)/g, "")
    .trim();
  const saetze = rumpf.split(/(?<=[.!?])\s+(?=[A-ZÄÖÜ])/);
  const ende = saetze.findIndex((satz) => AN_DEN_AGENTEN.test(satz));
  const fachlich = (ende < 0 ? saetze : saetze.slice(0, ende)).join(" ").trim();
  return alltag(fachlich || anweisung.trim());
}

/** Wer den Auftrag gegeben hat: Name aus dem Protokoll, sonst die Herkunft „Auftrag N“ der Aufgabenstellung. */
export function auftraggeber(v: Pick<Vorschlag, "gesagtVon" | "anweisung">): string {
  if (v.gesagtVon) return `Gesagt von ${v.gesagtVon}`;
  return /^Auftrag \d+\b/.test(v.anweisung.trim()) ? "Änderungsauftrag aus der Aufgabenstellung" : "Ohne Namen erfasst";
}

// ---------------------------------------------------------------------------------------------------------------
// Sätze und Tabellen der Freigabe-Seiten (UI-Regie v1): ein Kopfsatz, Zeilen ohne Codes, Probe als kleine Tabelle
// ---------------------------------------------------------------------------------------------------------------

const kurzFormat = new Intl.DateTimeFormat("de-AT", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "Europe/Vienna",
});

/** Zeitpunkt in Wiener Zeit als „05.11. 16:53“; ein ungültiger Wert bleibt, wie er ist. */
export function kurzZeit(iso: string): string {
  const datum = new Date(iso);
  if (Number.isNaN(datum.getTime())) return iso;
  const teil = (art: Intl.DateTimeFormatPartTypes) => kurzFormat.formatToParts(datum).find((t) => t.type === art)?.value ?? "";
  return `${teil("day")}.${teil("month")}. ${teil("hour")}:${teil("minute")}`;
}

/** Titel und Nummer eines Auftrags: „Auftrag 1, Dienstvertrag …: …“ → Nummer 1, Titel „Dienstvertrag …“. */
export function auftragKopf(anweisung: string): { nummer: string | null; titel: string } {
  const treffer = /^\s*Auftrag (\d+)\s*,?\s*([^:]{0,100}):/.exec(anweisung);
  if (treffer) {
    const rest = (treffer[2] ?? "").trim();
    const titel = rest ? rest.charAt(0).toUpperCase() + rest.slice(1) : `Auftrag ${treffer[1]}`;
    return { nummer: treffer[1] ?? null, titel: alltag(titel) };
  }
  const [satz = ""] = anweisung.trim().split(/(?<=[.!?])\s+/);
  const kurz = satz.length <= 90 ? satz.replace(/[.!?]$/, "") : `${satz.slice(0, 90).replace(/\s+\S*$/, "")} …`;
  return { nummer: null, titel: alltag(kurz || "Änderung an den Regeln") };
}

/** Was die Änderung an den Regeln tut, ohne Regelcodes: „Ändert eine Regel im Regelsatz v2“. */
export function aenderungSatz(v: Pick<Vorschlag, "typ" | "aenderungen" | "regelsatzZiel">): string {
  if (v.typ === "code_datei") return "Neue Sonderauswertung, sie ändert keine Zahl der Statistik";
  const n = Math.max(v.aenderungen.length, 1);
  const wo = v.regelsatzZiel === "ministerium" ? "für die Ministeriums-Lieferung" : `im Regelsatz ${v.regelsatzZiel}`;
  if (v.typ === "regel_neu") return n === 1 ? `Neue Regel ${wo}` : `${formatZahl(n)} neue Regeln ${wo}`;
  return n === 1 ? `Ändert eine Regel ${wo}` : `Ändert ${formatZahl(n)} Regeln ${wo}`;
}

/** Kopfsatz der Freigaben aus den Daten, etwa „3 Änderungen, alle mit Namen freigegeben.“ */
export function freigabenKopf(offen: number, entschieden: readonly { art: "freigegeben" | "abgelehnt" }[]): string {
  if (offen > 0) return offen === 1 ? "1 Änderung wartet auf Ihre Freigabe." : `${formatZahl(offen)} Änderungen warten auf Ihre Freigabe.`;
  const n = entschieden.length;
  if (n === 0) return "Noch hat kein Agent eine Änderung vorgeschlagen.";
  const abgelehnt = entschieden.filter((e) => e.art === "abgelehnt").length;
  if (abgelehnt === 0) return n === 1 ? "1 Änderung, mit Namen freigegeben." : `${formatZahl(n)} Änderungen, alle mit Namen freigegeben.`;
  if (abgelehnt === n) return n === 1 ? "1 Änderung, mit Namen abgelehnt." : `${formatZahl(n)} Änderungen, alle mit Namen abgelehnt.`;
  return `${formatZahl(n)} Änderungen mit Namen entschieden: ${formatZahl(n - abgelehnt)} freigegeben, ${formatZahl(abgelehnt)} abgelehnt.`;
}

const ROLLEN_DATIV: Record<string, string> = {
  datenmanagement: "vom Datenmanagement-Agenten",
  klassifikation: "vom Klassifikations-Agenten",
  qs: "vom Prüf-Agenten",
  reporting: "vom Berichts-Agenten",
};

const ANBIETER: Record<string, string> = {
  azure: "Azure",
  claude: "Claude",
  mistral: "Mistral",
  ollama: "Ollama",
  mock: "Testmodell",
};

/** „Vorgeschlagen vom Klassifikations-Agenten (Azure gpt-5-4-mini)“ */
export function vorgeschlagenVon(v: Pick<Vorschlag, "rolle" | "modell" | "provider">): string {
  const wer = ROLLEN_DATIV[v.rolle] ?? `von ${rollenName(v.rolle)}`;
  const anbieter = v.provider ? (ANBIETER[v.provider] ?? v.provider) : null;
  const modell = [anbieter, v.modell].filter(Boolean).join(" ");
  return `Vorgeschlagen ${wer}${modell ? ` (${modell})` : ""}`;
}

export interface ProbeKategorie {
  kategorie: string;
  vorher: number;
  nachher: number;
  /** Vorher getrennt gezählte Gruppen dieser Kategorie, z. B. „Angestellte mit Dienstvertrag“ 235.819. */
  vorherTeile: { wort: string; wert: number }[];
}

export interface ProbeTabelle {
  lieferung: string;
  /** Je Beschäftigungskategorie, alphabetisch (Angestellte, Arbeiter, Beamte …). */
  zeilen: ProbeKategorie[];
  gesamt: { vorher: number; nachher: number };
}

/**
 * Die Probe je Beschäftigungskategorie: Die Qualifikationscodes vorher und nachher werden über stat.klass_qualifikation
 * ihrer Kategorie zugeordnet; ein Code, der selbst eine Kategorie ist (Regelsatz v2), steht unter sich selbst.
 * Ohne gerechnete Probe null.
 */
export function probeJeKategorie(probe: unknown, kategorien: Kategorien): ProbeTabelle | null {
  const [monat] = probeMonate(probe);
  if (!monat) return null;
  const v = objekt(objekt(monat.vorher.je_merkmal).qualifikation);
  const n = objekt(objekt(monat.nachher.je_merkmal).qualifikation);
  const je = new Map<string, ProbeKategorie>();
  const eintrag = (code: string) => {
    const kategorie = kategorien[code]?.kategorie ?? code;
    return je.get(kategorie) ?? je.set(kategorie, { kategorie, vorher: 0, nachher: 0, vorherTeile: [] }).get(kategorie)!;
  };
  for (const [code, wert] of Object.entries(v)) {
    const e = eintrag(code);
    e.vorher += zahl(wert);
    if (zahl(wert) === 0) continue;
    const k = kategorien[code];
    const wort = !k || k.frei === null || code === k.kategorie ? (k?.kategorie ?? code) : `${k.kategorie} ${k.frei ? "freier Dienstvertrag" : "mit Dienstvertrag"}`;
    e.vorherTeile.push({ wort, wert: zahl(wert) });
  }
  // Dienstvertrag vor freiem Dienstvertrag, damit die Zeilen wie in der Aufgabe gelesen werden.
  for (const e of je.values()) e.vorherTeile.sort((a, b) => Number(a.wort.includes("freier")) - Number(b.wort.includes("freier")));
  for (const [code, wert] of Object.entries(n)) eintrag(code).nachher += zahl(wert);
  const zeilen = [...je.values()]
    .filter((z) => z.vorher !== 0 || z.nachher !== 0)
    .sort((a, b) => a.kategorie.localeCompare(b.kategorie, "de"));
  const summe = (seite: "vorher" | "nachher") => zeilen.reduce((s, z) => s + z[seite], 0);
  const gesamt = {
    vorher: monat.vorher.gesamt !== undefined ? zahl(monat.vorher.gesamt) : summe("vorher"),
    nachher: monat.nachher.gesamt !== undefined ? zahl(monat.nachher.gesamt) : summe("nachher"),
  };
  if (zeilen.length === 0 && gesamt.vorher === 0 && gesamt.nachher === 0) return null;
  return { lieferung: monat.lieferung, zeilen, gesamt };
}

/** Ein Beleg für die ganze Probe-Tabelle: je Kategorie vorher und nachher aus meta.vorschlag.probe, dazu Gesamt. */
export function probeTabelleBeleg(vorschlagIdWert: number, t: ProbeTabelle): Beleg {
  const basis = t.lieferung ? `v.probe->${literal(t.lieferung)}` : "v.probe";
  return {
    quelle: "meta.vorschlag",
    lieferung: t.lieferung || null,
    monat: t.lieferung || null,
    stand: "vorlaeufig",
    verweis: `Probe zu Vorschlag uc3/${vorschlagIdWert}, gerechnet und zurückgerollt`,
    sql: [
      "SELECT coalesce(k.beschaeftigungskategorie, q.code) AS kategorie,",
      "       sum(q.vorher) AS vorher, sum(q.nachher) AS nachher",
      "FROM meta.vorschlag v",
      "CROSS JOIN LATERAL (",
      "  SELECT coalesce(a.key, b.key) AS code,",
      "         coalesce(a.value::bigint, 0) AS vorher, coalesce(b.value::bigint, 0) AS nachher",
      `  FROM jsonb_each_text(${basis}->'vorher'->'je_merkmal'->'qualifikation') a`,
      `  FULL JOIN jsonb_each_text(${basis}->'nachher'->'je_merkmal'->'qualifikation') b ON b.key = a.key`,
      ") q",
      "LEFT JOIN stat.klass_qualifikation k ON k.code = q.code",
      `WHERE v.id = ${literal(vorschlagIdWert)}`,
      "GROUP BY 1",
      "UNION ALL",
      `SELECT 'Gesamt', (${basis}->'vorher'->>'gesamt')::bigint, (${basis}->'nachher'->>'gesamt')::bigint`,
      `FROM meta.vorschlag v WHERE v.id = ${literal(vorschlagIdWert)};`,
    ].join("\n"),
  };
}

export interface ProtokollZeile {
  schluessel: string;
  satz: string;
  name: string;
  zeit: string;
  art: "freigegeben" | "abgelehnt";
}

/**
 * Weitere Einträge im Protokoll, die zu keinem Vorschlag gehören, in Worten. Die Regelstände eines Regelsatzes
 * (einer je Monat) werden zu einer Zeile, etwa „Regeln von Regelsatz v2 für 24 Monate festgehalten“.
 */
export function protokollZeilen(zeilen: readonly ErledigtZeile[]): ProtokollZeile[] {
  const ergebnis: ProtokollZeile[] = [];
  const gruppen = new Map<string, { regelsatz: string; name: string; zeit: string; monate: string[] }>();
  for (const z of zeilen) {
    if (z.vorschlag) continue;
    if (z.regelstand) {
      const schluessel = `${z.regelstand.regelsatz}|${z.name}`;
      const g = gruppen.get(schluessel) ?? gruppen.set(schluessel, { regelsatz: z.regelstand.regelsatz, name: z.name, zeit: z.zeit, monate: [] }).get(schluessel)!;
      if (z.zeit > g.zeit) g.zeit = z.zeit;
      g.monate.push(z.regelstand.lieferung);
      continue;
    }
    const satz = z.anweisung ? auftragKopf(z.anweisung).titel : alltag(z.geaendert ?? "Änderung");
    ergebnis.push({ schluessel: z.schluessel, satz, name: z.name, zeit: z.zeit, art: z.art });
  }
  for (const [schluessel, g] of gruppen) {
    const monate = [...new Set(g.monate)].sort();
    const name = (m: string) => (istMonat(m) ? monatName(m) : m);
    const satz =
      monate.length === 1
        ? `Regeln von Regelsatz ${g.regelsatz} für ${name(monate[0]!)} festgehalten`
        : `Regeln von Regelsatz ${g.regelsatz} für ${formatZahl(monate.length)} Monate festgehalten, ${name(monate[0]!)} bis ${name(monate.at(-1)!)}`;
    ergebnis.push({ schluessel: `r-${schluessel}`, satz, name: g.name, zeit: g.zeit, art: "freigegeben" });
  }
  return ergebnis.sort((a, b) => b.zeit.localeCompare(a.zeit));
}

/**
 * Warum ein Vorschlag keine Probe mit vorher und nachher hat. Eine Regel für die Ministeriums-Lieferung und eine
 * Sonderauswertung ändern keine Zählung des Bestands; sonst ist die Probe nur noch nicht gerechnet.
 */
export function ohneProbeSatz(v: Pick<Vorschlag, "typ" | "regelsatzZiel">): string {
  if (v.regelsatzZiel === "ministerium")
    return "Diese Regel ändert keine Zählung des Bestands. Sie legt die Ministeriums-Lieferung an, deshalb gibt es kein vorher und nachher.";
  if (v.typ === "code_datei")
    return "Diese Sonderauswertung ändert keine Zählung des Bestands, deshalb gibt es kein vorher und nachher.";
  return "Die Probe ist noch nicht gerechnet, deshalb fehlen die Zahlen vorher und nachher.";
}
