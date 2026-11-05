import { monatName } from "./monat";

/**
 * Anzeigetext aus der Datenbank in die Wortliste von docs/sprache.md bringen (Sichtprüfung bb, #18):
 * „Verhältnis“ allein wird „Beschäftigungsverhältnis“, Monate als JJJJ-MM werden ausgeschrieben.
 * Nur für sichtbaren Text. Nie auf SQL, Belege, Regelnamen, Hashes oder Werte anwenden, mit denen die Logik
 * rechnet oder filtert (etwa `lieferungen` in `rueckfrageBetrifft`).
 */

// Großes V als eigenes Wort: nicht in „Beschäftigungsverhältnis“, nicht nach Bindestrich, nicht „im Verhältnis zu“.
const VERHAELTNIS = /(?<![\p{L}\p{N}_-])Verhältnis(se|sen|ses)?(?![\p{L}\p{N}_-])/gu;
const IM_VERHAELTNIS_ZU = /\bim\s+$/i;
const NACH_ZU = /^\s+zu[mr]?\b/;

// „lieferung_2025-10“ (Schreibweise der Datenbank) wird „Lieferung Oktober 2025“.
const LIEFERUNG_CODE = /(?<![\p{L}\p{N}_-])lieferung_(\d{4}-(?:0[1-9]|1[0-2]))(?![\p{L}\p{N}_'-])/giu;
// JJJJ-MM allein: nicht Teil eines Datums (JJJJ-MM-TT), eines Hashes, eines Codes oder eines Literals in Hochkommas.
const MONAT = /(?<![\p{L}\p{N}_'/.-])(\d{4}-(?:0[1-9]|1[0-2]))(?![\p{L}\p{N}_'/-]|\.\d)/gu;

// „Satz“ und „Sätze“ als eigenes Wort meinen in den Texten der Datenbank eine Zeile der Lieferung (docs/sprache.md).
const SATZ = /(?<![\p{L}\p{N}_-])(Satz|Sätze|Sätzen)(?![\p{L}\p{N}_-])/gu;
const ZEILE: Record<string, string> = { Satz: "Zeile", Sätze: "Zeilen", Sätzen: "Zeilen" };

// Artikel vor „Satz“ passen zur „Zeile“ (weiblich): „zu einem Satz“ wird „zu einer Zeile“.
const ARTIKEL_SATZ = /\b(einem|einen|ein|jeder|jeden|der|den|dem|kein|keinen|keinem)\s+Satz\b/g;
const ARTIKEL_ZEILE: Record<string, string> = {
  einem: "einer", einen: "eine", ein: "eine", jeder: "jede", jeden: "jede", der: "die", den: "die", dem: "der",
  kein: "keine", keinen: "keine", keinem: "keiner",
};

export function alltag(text: string): string {
  return text
    .replace(ARTIKEL_SATZ, (_ganz: string, artikel: string) => `${ARTIKEL_ZEILE[artikel] ?? artikel} Zeile`)
    .replace(SATZ, (wort: string) => ZEILE[wort] ?? wort)
    .replace(VERHAELTNIS, (ganz: string, endung: string | undefined, stelle: number, quelle: string) => {
      if (IM_VERHAELTNIS_ZU.test(quelle.slice(0, stelle)) && NACH_ZU.test(quelle.slice(stelle + ganz.length))) return ganz;
      return `Beschäftigungsverhältnis${endung ?? ""}`;
    })
    .replace(LIEFERUNG_CODE, (_ganz: string, monat: string) => `Lieferung ${monatName(monat)}`)
    .replace(MONAT, (_ganz: string, monat: string) => monatName(monat));
}

/** Wie `alltag`, lässt `null` und `undefined` stehen. */
export function alltagOder<T extends string | null | undefined>(text: T): T {
  return (typeof text === "string" ? alltag(text) : text) as T;
}
