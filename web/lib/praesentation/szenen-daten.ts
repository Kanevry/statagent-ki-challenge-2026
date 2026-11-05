/**
 * Inhalt einer Folie so zerlegt, wie die animierten Szenen ihn brauchen (#59, Lane E5). Reine Funktionen ohne
 * Dateizugriff, damit Server, Browser und Tests sie gleich nutzen. Jeder sichtbare Satz und jede Zahl einer Szene
 * kommt über diese Funktionen aus dem Markdown; die Szenen selbst schreiben keinen Inhalt fest.
 * Aus folien.ts nur Typen importieren: die Datei lädt node:fs und darf nicht in den Browser.
 */
import { inlineText, parseInline, type Block, type Inline } from "./markdown";
import type { Folie } from "./folien";

type Absatz = Extract<Block, { art: "absatz" }>;
type Liste = Extract<Block, { art: "liste" }>;
type Tabelle = Extract<Block, { art: "tabelle" }>;

const HERKUNFT = /^Herkunft:/i;

/** Text der ersten Überschrift `#`, oder `undefined`, wenn die Folie keine hat. */
export function ueberschrift(folie: Folie): string | undefined {
  const h = folie.inhalt.find((b) => b.art === "ueberschrift" && b.stufe === 1);
  return h?.art === "ueberschrift" ? inlineText(h.inline) : undefined;
}

/** Text der ersten Überschrift `#`, sonst der Titel aus dem Frontmatter. */
export function kopfzeile(folie: Folie): string {
  return ueberschrift(folie) ?? folie.titel;
}

/** Absätze der Folie in Reihenfolge als Text, ohne die `Herkunft:`-Zeile. */
export function absatzTexte(folie: Folie): string[] {
  return folie.inhalt
    .filter((b): b is Absatz => b.art === "absatz")
    .map((b) => inlineText(b.inline))
    .filter((t) => !HERKUNFT.test(t));
}

/** Die Zeile `Herkunft: …`, wie sie im Markdown steht, oder `undefined`. */
export function herkunft(folie: Folie): string | undefined {
  const b = folie.inhalt.find((x) => x.art === "absatz" && HERKUNFT.test(inlineText(x.inline)));
  return b?.art === "absatz" ? inlineText(b.inline) : undefined;
}

/** Punkte der ersten Liste der Folie. */
export function listenPunkte(folie: Folie): Inline[][] {
  return folie.inhalt.find((b): b is Liste => b.art === "liste")?.punkte ?? [];
}

/** Alle Tabellen der Folie als Text: Kopf und Zeilen. */
export function tabellen(folie: Folie): { kopf: string[]; zeilen: string[][] }[] {
  return folie.inhalt
    .filter((b): b is Tabelle => b.art === "tabelle")
    .map((t) => ({ kopf: t.kopf.map(inlineText), zeilen: t.zeilen.map((z) => z.map(inlineText)) }));
}

/** Erste Tabelle als Text: Kopf und Zeilen. */
export function tabelle(folie: Folie): { kopf: string[]; zeilen: string[][] } | undefined {
  return tabellen(folie)[0];
}

/**
 * Ein Listenpunkt der Form `**Kopf:** Rest`. Der Kopf verliert Doppelpunkt und Punkt am Ende und darf selbst
 * `code` enthalten; der Rest ist reiner Text. Ohne fetten Anfang ist der Kopf leer.
 */
export function kopfUndRest(punkt: readonly Inline[]): { kopf: Inline[]; rest: string } {
  const [erstes, ...weitere] = punkt;
  if (erstes?.art !== "fett") return { kopf: [], rest: inlineText(punkt).trim() };
  return { kopf: parseInline(erstes.text.replace(/[:.]\s*$/, "")), rest: inlineText(weitere).trim() };
}

/** Zahl in deutscher Schreibweise (`392.236`, `−0,5`) als Number; `NaN`, wenn keine Zahl darin steht. */
export function zahlWert(text: string | undefined): number {
  const treffer = /[-−]?\d[\d.]*(?:,\d+)?/.exec(text ?? "");
  if (!treffer) return Number.NaN;
  return Number(treffer[0].replace("−", "-").replace(/\./g, "").replace(",", "."));
}

/**
 * Bild-Kennung aus `screenshot:` im Frontmatter. `SC7`, `sc07` und `SC07` werden `SC07`; ein Dateiname ohne Endung
 * wie `freigabe-echt` bleibt, wie er ist. Leer oder `null`: keine Kennung.
 */
export function screenshotKennung(folie: Folie): string | undefined {
  const roh = folie.daten.screenshot?.trim();
  if (!roh) return undefined;
  const sc = /^sc0*(\d+)$/i.exec(roh);
  if (sc?.[1]) return `SC${sc[1].padStart(2, "0")}`;
  return /^[\w-]+$/.test(roh) ? roh : undefined;
}

/** Übergänge aus dem Frontmatter `uebergang: C-C J-J Q-R J-K` als Paare (alter Code, neuer Code). */
export function uebergaenge(text: string | undefined): [string, string][] {
  return (text ?? "")
    .split(/\s+/)
    .map((p) => p.split("-"))
    .filter((p): p is [string, string] => p.length === 2 && p[0] !== "" && p[1] !== "");
}
