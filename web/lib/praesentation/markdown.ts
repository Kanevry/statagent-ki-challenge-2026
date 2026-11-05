/**
 * Kleiner Markdown-Parser für die Folien (#59). Keine Abhängigkeit, kein HTML: das Ergebnis sind Daten,
 * aus denen React-Elemente entstehen. Unterstützt werden Überschriften (`#`, `##`), Absätze, Listen (`-`, `1.`),
 * einfache Tabellen, `**fett**` und `` `code` ``. Alles andere bleibt Text.
 */

export type Inline = { art: "text" | "fett" | "code"; text: string };

export type Block =
  | { art: "ueberschrift"; stufe: 1 | 2; inline: Inline[] }
  | { art: "absatz"; inline: Inline[] }
  | { art: "liste"; geordnet: boolean; punkte: Inline[][] }
  | { art: "tabelle"; kopf: Inline[][]; zeilen: Inline[][][] };

const INLINE = /(\*\*[^*\n]+\*\*|`[^`\n]+`)/;

/** Zerlegt eine Zeile in Text, Fett und Code. Nicht geschlossene Zeichen bleiben als Text stehen. */
export function parseInline(text: string): Inline[] {
  const teile: Inline[] = [];
  for (const stueck of text.split(INLINE)) {
    if (stueck === "") continue;
    if (stueck.startsWith("**") && stueck.endsWith("**") && stueck.length > 4) {
      teile.push({ art: "fett", text: stueck.slice(2, -2) });
    } else if (stueck.startsWith("`") && stueck.endsWith("`") && stueck.length > 2) {
      teile.push({ art: "code", text: stueck.slice(1, -1) });
    } else {
      teile.push({ art: "text", text: stueck });
    }
  }
  return teile;
}

/** Reiner Text ohne Auszeichnung, z. B. für Titel und Beschriftungen. */
export function inlineText(inline: readonly Inline[]): string {
  return inline.map((i) => i.text).join("");
}

const UEBERSCHRIFT = /^(#{1,6})\s+(.*?)\s*#*\s*$/;
const PUNKT = /^\s*(?:([-*])|(\d+)[.)])\s+(.*)$/;
const KOMMENTAR = /^\s*<!--.*-->\s*$/;

function istTabellenZeile(zeile: string): boolean {
  return zeile.trim().startsWith("|") && zeile.trim().endsWith("|") && zeile.trim().length > 1;
}

function istTrennzeile(zeile: string): boolean {
  return istTabellenZeile(zeile) && /^[\s|:-]+$/.test(zeile) && zeile.includes("-");
}

function zellen(zeile: string): Inline[][] {
  return zeile
    .trim()
    .slice(1, -1)
    .split("|")
    .map((z) => parseInline(z.trim()));
}

/** Zerlegt Markdown-Text in Blöcke. Leere Zeilen trennen Absätze; HTML-Kommentare werden übergangen. */
export function parseBlocks(quelle: string): Block[] {
  const zeilen = quelle.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  let absatz: string[] = [];
  let liste: { geordnet: boolean; punkte: string[] } | null = null;

  const absatzSchliessen = () => {
    if (absatz.length > 0) blocks.push({ art: "absatz", inline: parseInline(absatz.join(" ")) });
    absatz = [];
  };
  const listeSchliessen = () => {
    if (liste) blocks.push({ art: "liste", geordnet: liste.geordnet, punkte: liste.punkte.map(parseInline) });
    liste = null;
  };

  for (let i = 0; i < zeilen.length; i++) {
    const zeile = zeilen[i] ?? "";
    if (zeile.trim() === "") {
      absatzSchliessen();
      listeSchliessen();
      continue;
    }
    if (KOMMENTAR.test(zeile)) continue;

    const ueberschrift = UEBERSCHRIFT.exec(zeile);
    if (ueberschrift) {
      absatzSchliessen();
      listeSchliessen();
      const text = ueberschrift[2] ?? "";
      blocks.push({ art: "ueberschrift", stufe: ueberschrift[1] === "#" ? 1 : 2, inline: parseInline(text) });
      continue;
    }

    if (istTabellenZeile(zeile) && istTrennzeile(zeilen[i + 1] ?? "")) {
      absatzSchliessen();
      listeSchliessen();
      const kopf = zellen(zeile);
      const reihen: Inline[][][] = [];
      i += 2;
      while (i < zeilen.length && istTabellenZeile(zeilen[i] ?? "")) {
        reihen.push(zellen(zeilen[i] ?? ""));
        i++;
      }
      i--;
      blocks.push({ art: "tabelle", kopf, zeilen: reihen });
      continue;
    }

    const punkt = PUNKT.exec(zeile);
    if (punkt) {
      absatzSchliessen();
      const geordnet = punkt[2] !== undefined;
      if (liste && liste.geordnet !== geordnet) listeSchliessen();
      liste ??= { geordnet, punkte: [] };
      liste.punkte.push(punkt[3] ?? "");
      continue;
    }

    // Eingerückte Fortsetzung eines Listenpunkts
    if (liste && /^\s+\S/.test(zeile)) {
      liste.punkte[liste.punkte.length - 1] += ` ${zeile.trim()}`;
      continue;
    }

    listeSchliessen();
    absatz.push(zeile.trim());
  }
  absatzSchliessen();
  listeSchliessen();
  return blocks;
}
