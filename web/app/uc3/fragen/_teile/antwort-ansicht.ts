import type { UcAntwort } from "@kic/ui/antwortform";
import { istMonat, monatName } from "@/components/uc3/monat";

// Darstellung einer Antwort von „Fragen an die Daten“ (UI-Regie v1), ohne Logik der API: was das Programm
// verstanden hat, eine Tabelle aus den Bezeichnungen und die Vorschläge einer Rückfrage als Knöpfe.

type Zahl = UcAntwort["zahlen"][number];

/** Monat der Antwort ausgeschrieben, aus dem ersten Beleg. */
export function antwortMonat(antwort: UcAntwort): string | null {
  const b = antwort.belege[0];
  const m = b?.monat ?? b?.lieferung ?? null;
  return m && istMonat(m) ? monatName(m) : null;
}

/** „Beschäftigungsverhältnisse (Wien, Gesundheits- und Sozialwesen)“ → Was und Wo getrennt. */
export function teileBezeichnung(bezeichnung: string): { was: string; wo: string | null } {
  const klammer = /^(.*?)\s*\((.+)\)\s*$/.exec(bezeichnung);
  if (klammer) return { was: klammer[1]!.trim(), wo: klammer[2]!.trim() };
  const [was = bezeichnung, ...rest] = bezeichnung.split(", ");
  return { was, wo: rest.length > 0 ? rest.join(", ") : null };
}

/** „Verstanden: Wien, Gesundheits- und Sozialwesen, März 2025“; null, wenn nichts Erkanntes vorliegt. */
export function verstandenSatz(antwort: UcAntwort): string | null {
  const [erste] = antwort.zahlen;
  const wo = antwort.zahlen.length === 1 && erste ? teileBezeichnung(erste.bezeichnung).wo : null;
  const teile = [wo, antwortMonat(antwort)].filter(Boolean);
  return teile.length > 0 ? `Verstanden: ${teile.join(", ")}` : null;
}

/** Erster Satz eines Textes; ein Punkt nach einer Zahl („31. März“) beendet keinen Satz. */
export function ersterSatz(text: string): string {
  const [satz = text] = text.trim().split(/(?<=[^\d\s][.!?])\s+(?=[A-ZÄÖÜ])/);
  return satz;
}

/**
 * Kopfsatz einer Antwort mit Tabelle: der erste Satz ohne Angaben, die nichts eingrenzen („Branche: alle“).
 * Aus „Verstanden: Oktober 2025, je Bundesland, Branche: alle.“ wird „Verstanden: Oktober 2025, je Bundesland.“
 */
export function kopfSatz(text: string): string {
  return ersterSatz(text).replace(/,\s*[^,:.]+:\s*alle(?=[,.]|$)/g, "");
}

/** Steht „Verstanden“ schon im Kopfsatz, entfällt die zweite Zeile „Verstanden: …“ darunter. */
export function kopfSagtVerstanden(kopf: string): boolean {
  return kopf.startsWith("Verstanden");
}

/** Summenzeile einer Tabelle, etwa „Alle Bundesländer“ oder „alle Wirtschaftsbereiche (Summe der Zeilen)“. */
export function istSummenzeile(titel: string): boolean {
  return /^alle\b/i.test(titel.trim());
}

export type AntwortTabelle = {
  /** Spaltentitel, etwa „Männer“ und „Frauen“; eine Spalte „Wert“, wenn nichts zu teilen ist. */
  spalten: { titel: string; einheit: string | null }[];
  zeilen: { titel: string; werte: (number | null)[] }[];
};

function einheitWort(einheit: string | null | undefined): string | null {
  if (!einheit || einheit === "Anzahl") return null;
  return einheit === "Prozent" ? "%" : einheit;
}

/**
 * Bildet aus den Bezeichnungen eine schlichte Tabelle. Teile vor dem ersten Komma, die alle Zahlen gemeinsam haben,
 * fallen weg; der nächste Teil wird zur Spalte (Männer, Frauen oder Fluktuation, Zugänge …), der Rest zur Zeile.
 * Passt das nicht (zu viele Spalten, doppelte Zellen), steht je Zahl eine Zeile mit einer Spalte „Wert“.
 */
export function antwortTabelle(zahlen: readonly Zahl[]): AntwortTabelle {
  const teile = zahlen.map((z) => z.bezeichnung.split(", "));
  let gemeinsam = 0;
  while (teile.length > 1 && teile.every((t) => t.length > gemeinsam + 1 && t[gemeinsam] === teile[0]![gemeinsam])) gemeinsam += 1;
  const rest = teile.map((t) => t.slice(gemeinsam));
  const spaltenNamen = [...new Set(rest.map((t) => t[0] ?? ""))];
  const zellen = new Map<string, Zahl>();
  let passt = spaltenNamen.length >= 2 && spaltenNamen.length <= 5 && rest.every((t) => t.length >= 2);
  if (passt) {
    rest.forEach((t, i) => {
      const schluessel = `${t.slice(1).join(", ")}|${t[0]}`;
      if (zellen.has(schluessel)) passt = false;
      zellen.set(schluessel, zahlen[i]!);
    });
  }
  if (!passt) {
    const einheit = einheitWort(zahlen[0]?.einheit);
    const gleicheEinheit = zahlen.every((z) => einheitWort(z.einheit) === einheit);
    return {
      spalten: [{ titel: "Wert", einheit: gleicheEinheit ? einheit : null }],
      zeilen: zahlen.map((z, i) => ({ titel: rest[i]!.join(", ") || z.bezeichnung, werte: [z.wert] })),
    };
  }
  const zeilenNamen = [...new Set(rest.map((t) => t.slice(1).join(", ")))];
  return {
    spalten: spaltenNamen.map((s) => {
      const z = zahlen[rest.findIndex((t) => t[0] === s)];
      return { titel: s, einheit: einheitWort(z?.einheit) };
    }),
    zeilen: zeilenNamen.map((zeile) => ({
      titel: zeile,
      werte: spaltenNamen.map((s) => zellen.get(`${zeile}|${s}`)?.wert ?? null),
    })),
  };
}

/** Vorschläge einer Rückfrage: die Texte in „…“, höchstens drei, etwa „Beschäftigte Dezember 2025“. */
export function rueckfrageVorschlaege(text: string): string[] {
  const treffer = [...text.matchAll(/„([^“”"]{3,120})[“”"]/g)].map((t) => t[1]!.trim());
  return [...new Set(treffer)].slice(0, 3);
}
