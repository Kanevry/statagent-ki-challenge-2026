import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { inlineText, parseBlocks, type Block } from "./markdown";

/** Die feste Menge an Layouts. Alles andere wird zu `text`. Format: web/content/slides/README.md */
export const LAYOUTS = ["titel", "text", "schritte", "zahl", "live"] as const;
export type Layout = (typeof LAYOUTS)[number];

/** Andere Namen für dieselben Layouts (die Folien-Session schreibt „cover“). */
const ALIAS: Record<string, Layout> = { cover: "titel" };

export interface Folie {
  /** Dateiname ohne Endung, z. B. `01-titel`. */
  id: string;
  titel: string;
  layout: Layout;
  /** Nur bei `live`: erlaubte Route aus der Registry, z. B. `/uc3`. */
  route?: string;
  /** Zeitangabe wie `0:00` oder `3:15–4:15`, nur zur Anzeige. */
  zeit?: string;
  /** Nur bei `zahl`: die große Zahl; fehlt sie, trägt die erste Überschrift die Zahl. */
  zahl?: string;
  /** Nur bei `zahl`: die Beleg-Zeile unter der Zahl. */
  beleg?: string;
  inhalt: Block[];
  notizen: Block[];
}

const NOTIZ_MARKE = /^\s*(?:<!--\s*notizen\s*-->|##\s+Sprechernotizen)\s*$/i;
const SCHLUESSEL = /^([A-Za-z_][\w-]*)\s*:\s*(.*)$/;

/** Wert einer Frontmatter-Zeile: Anführungszeichen weg, leer und `null` gelten als nicht gesetzt. */
function wert(roh: string): string | undefined {
  let text = roh.trim();
  if (text.length >= 2 && (text[0] === '"' || text[0] === "'") && text.at(-1) === text[0]) text = text.slice(1, -1);
  return text === "" || text === "null" ? undefined : text;
}

function trenneFrontmatter(zeilen: string[]): { daten: Record<string, string>; rest: string[] } {
  if (zeilen[0]?.trim() !== "---") return { daten: {}, rest: zeilen };
  const ende = zeilen.findIndex((z, i) => i > 0 && z.trim() === "---");
  if (ende === -1) return { daten: {}, rest: zeilen };
  const daten: Record<string, string> = {};
  for (const zeile of zeilen.slice(1, ende)) {
    const treffer = SCHLUESSEL.exec(zeile);
    const v = treffer ? wert(treffer[2] ?? "") : undefined;
    if (treffer && v !== undefined) daten[treffer[1] ?? ""] = v;
  }
  return { daten, rest: zeilen.slice(ende + 1) };
}

/** Erlaubt nur Routen im eigenen Auftritt: `/pfad`, nie `//host` oder `javascript:`. */
export function istInterneRoute(route: string | undefined): route is string {
  return typeof route === "string" && /^\/(?!\/)[\w\-./]*$/.test(route);
}

/** Liest eine Folie aus dem Text ihrer Datei. Wirft nie: fehlende Angaben bekommen Ersatzwerte. */
export function parseFolie(dateiname: string, quelle: string): Folie {
  const id = dateiname.replace(/\.md$/i, "");
  const { daten, rest } = trenneFrontmatter(quelle.replace(/\r\n?/g, "\n").split("\n"));
  const marke = rest.findIndex((z) => NOTIZ_MARKE.test(z));
  const inhalt = parseBlocks((marke === -1 ? rest : rest.slice(0, marke)).join("\n"));
  const notizen = marke === -1 ? [] : parseBlocks(rest.slice(marke + 1).join("\n"));

  const ersteUeberschrift = inhalt.find((b) => b.art === "ueberschrift");
  const angefragt = (daten.layout ?? "").toLowerCase();
  const layout = ALIAS[angefragt] ?? (LAYOUTS.find((l) => l === angefragt) ?? "text");
  const folie: Folie = {
    id,
    titel: daten.titel ?? (ersteUeberschrift ? inlineText(ersteUeberschrift.inline) : id.replace(/^\d+[-_ ]*/, "")),
    layout,
    inhalt,
    notizen,
  };
  if (layout === "live" && daten.route !== undefined) folie.route = daten.route;
  if (daten.zeit !== undefined) folie.zeit = daten.zeit;
  if (daten.zahl !== undefined) folie.zahl = daten.zahl;
  if (daten.beleg !== undefined) folie.beleg = daten.beleg;
  return folie;
}

/** Ordner der Folien, vom Arbeitsverzeichnis `web/` aus. */
export const FOLIEN_ORDNER = path.join(process.cwd(), "content", "slides");

/** Liest alle Folien eines Ordners, sortiert nach Dateiname (Zahlen als Zahlen: `2-` vor `10-`). Fehlt der Ordner, ist die Liste leer. */
export function leseFolien(ordner: string = FOLIEN_ORDNER): Folie[] {
  let namen: string[];
  try {
    // Die Folien kommen über outputFileTracingIncludes in den Build (next.config.ts); ohne den Kommentar
    // würde Turbopack wegen des variablen Pfads das ganze Projekt mitnehmen.
    namen = readdirSync(/* turbopackIgnore: true */ ordner);
  } catch {
    return [];
  }
  return namen
    .filter((n) => /\.md$/i.test(n) && !/^readme\.md$/i.test(n))
    .sort((a, b) => a.localeCompare(b, "de", { numeric: true }))
    .map((n) => parseFolie(n, readFileSync(/* turbopackIgnore: true */ path.join(ordner, n), "utf8")));
}

/** Anfang einer Zeitangabe: `3:15–4:15` wird `3:15`. */
export function zeitStart(zeit: string | undefined): string | undefined {
  return zeit?.split(/\s*[–—-]\s*/)[0]?.trim() || undefined;
}

/** Zeitangabe zum Vorlesen und Anzeigen ohne Strich: `3:15–4:15` wird `3:15 bis 4:15`. */
export function zeitText(zeit: string | undefined): string | undefined {
  return zeit?.split(/\s*[–—-]\s*/).join(" bis ") || undefined;
}
