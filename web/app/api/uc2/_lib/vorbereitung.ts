import { mockBerichtRoh, mockFall } from "./mock";
import { mockErzwungen, ruftApi, type Modus } from "./proxy";

// Alles, was die Startseite (U2-0) vor dem ersten Klick braucht: der Fall, die Auswahl der Akteure mit Belegzahl und
// welche Modelle wählbar sind. Die Liste der möglichen Akteure kennt die API erst nach einem Lauf; bis dahin kommt sie
// aus dem aufgezeichneten Fall. `herkunft` sagt das ehrlich: Fall und Belegzahlen sind immer ein Beispiel aus einer
// Aufzeichnung, auch wenn die API läuft (`modus: "live"`). Echte Daten gibt es erst mit einer Kandidatenliste der API (#132).

export interface AkteurAuswahl {
  akteur: string;
  belegzahl: number;
  /** Vorschlag des Moderators aus dem aufgezeichneten Lauf. */
  vorgeschlagen: boolean;
}

export interface ModellWahl {
  id: "azure" | "claude" | "ollama";
  label: string;
  verfuegbar: boolean;
  /** Sichtbare Meldung, wenn das Modell nicht gewählt werden kann. */
  meldung?: string;
}

export interface Vorbereitung {
  /** "vorfuehrung": keine Python-API, es läuft die aufgezeichnete Verhandlung ohne Sprachmodell. */
  modus: Modus;
  /** Woher Fall und Belegzahlen stammen. Heute immer "aufzeichnung", nie "api". */
  herkunft: "aufzeichnung";
  fall: { id: string; frage: string; stichtag: string; paket: string; maxAkteure: number };
  akteure: AkteurAuswahl[];
  modelle: ModellWahl[];
}

export function ollamaKonfiguriert(): boolean {
  return Boolean(process.env.OLLAMA_MODEL) || (mockErzwungen() && process.env.UC2_OLLAMA === "1");
}

export function modellWahl(): ModellWahl[] {
  const ollama = ollamaKonfiguriert();
  return [
    { id: "azure", label: "azure", verfuegbar: true },
    { id: "claude", label: "claude", verfuegbar: true },
    {
      id: "ollama",
      label: "ollama · lokal · Ersatz",
      verfuegbar: ollama,
      meldung: ollama ? undefined : "Das lokale Modell ist hier nicht eingerichtet.",
    },
  ];
}

/** Ist eine Python-API da? Ein kurzer Blick auf die Liste, ohne Modellaufruf. */
export async function apiErreichbar(): Promise<boolean> {
  if (mockErzwungen()) return false;
  const antwort = await ruftApi("/faelle", { frist: 800 });
  return antwort !== null && antwort.ok;
}

export async function ladeVorbereitung(): Promise<Vorbereitung> {
  const api = await apiErreichbar();
  const teilnahme = (mockBerichtRoh.teilnahme ?? []) as { akteur: string; belegzahl: number; eingeladen: boolean }[];
  const erfahren = (mockBerichtRoh.experte ?? {}) as { beschreibung?: string };
  return {
    modus: api ? "live" : "vorfuehrung",
    herkunft: "aufzeichnung",
    fall: {
      id: String(mockFall.fall_name ?? "wartezeiten"),
      frage: String(mockFall.frage ?? ""),
      stichtag: String(mockFall.stichtag ?? ""),
      paket: erfahren.beschreibung ?? "",
      maxAkteure: 6,
    },
    akteure: teilnahme.map((t) => ({ akteur: t.akteur, belegzahl: t.belegzahl, vorgeschlagen: t.eingeladen })),
    modelle: modellWahl(),
  };
}
