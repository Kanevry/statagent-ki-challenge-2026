"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { frageSchema, webAntwortSchema, type WebAntwort } from "./antwort";
import { formatAufnahme, pruefeReplay } from "./replay";
import pflege from "./fixtures/pflege.json";

// Zustand des Lotsen für alle Seiten unter /uc1 (liegt im Layout, damit „Erkannte Leistungen“ nach dem Wechsel
// der Seite dieselben Antworten zeigt). Die Sitzung lebt nur im React-Zustand, nicht im localStorage.

export interface Wechsel {
  eingabe: string;
  antwort: WebAntwort;
}

export type Lage =
  | { art: "leer" }
  | { art: "laden" }
  | { art: "bereit" }
  | { art: "fehler"; meldung: string; replay: boolean };

export interface Einstellungen {
  sprache: "de" | "en";
  einfach: boolean;
}

interface LotseWert {
  verlauf: readonly Wechsel[];
  lage: Lage;
  /** Gesetzt, solange eine Aufnahme statt einer Live-Antwort läuft oder zu sehen ist. */
  aufnahme: string | null;
  entwurf: string;
  setEntwurf: (text: string) => void;
  antwortEntwurf: string;
  setAntwortEntwurf: (text: string) => void;
  einstellungen: Einstellungen;
  setEinstellungen: (neu: Einstellungen) => void;
  /** Neue Situation: beginnt eine neue Sitzung. */
  erzaehlen: (text: string) => Promise<void>;
  /** Antwort auf eine Rückfrage: bleibt in der Sitzung. */
  antworten: (text: string) => Promise<void>;
  beispielAbspielen: () => Promise<void>;
}

const LotseKontext = createContext<LotseWert | null>(null);

export function useLotse(): LotseWert {
  const wert = useContext(LotseKontext);
  if (!wert) throw new Error("useLotse außerhalb von LotseAnbieter");
  return wert;
}

/** Pause zwischen Eingabe und Antwort im Replay, damit man sieht, was gefragt wurde. */
export const REPLAY_PAUSE_MS = 900;

const warte = (ms: number) => new Promise<void>((fertig) => setTimeout(fertig, ms));

async function frageSenden(
  text: string,
  sitzung: string | undefined,
  { sprache, einfach }: Einstellungen,
): Promise<{ antwort: WebAntwort } | { meldung: string; replay: boolean }> {
  const eingabe = frageSchema.safeParse({ text, sitzung, stil: einfach ? "einfach" : "standard", sprache });
  if (!eingabe.success) return { meldung: eingabe.error.issues[0]?.message ?? "Die Eingabe ist ungültig.", replay: false };
  let antwort: Response;
  try {
    antwort = await fetch("/api/uc1/frage", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(eingabe.data),
      cache: "no-store",
    });
  } catch {
    return { meldung: "Keine Verbindung zum Server.", replay: true };
  }
  const daten: unknown = await antwort.json().catch(() => null);
  if (!antwort.ok) {
    const feld = (name: string) =>
      daten && typeof daten === "object" && name in daten ? (daten as Record<string, unknown>)[name] : undefined;
    const meldung = typeof feld("fehler") === "string" ? (feld("fehler") as string) : "Der Lotse hat nicht geantwortet.";
    // Sperrt ein Proxy POST (405) ohne JSON, gilt dasselbe wie in der Online-Demo.
    return { meldung, replay: feld("replay") === true || antwort.status === 405 };
  }
  const geprueft = webAntwortSchema.safeParse(daten);
  return geprueft.success
    ? { antwort: geprueft.data }
    : { meldung: "Die Antwort kam in einem unerwarteten Format.", replay: true };
}

export function LotseAnbieter({ children }: { children: ReactNode }) {
  const [verlauf, setVerlauf] = useState<readonly Wechsel[]>([]);
  const [lage, setLage] = useState<Lage>({ art: "leer" });
  const [aufnahme, setAufnahme] = useState<string | null>(null);
  const [entwurf, setEntwurf] = useState("");
  const [antwortEntwurf, setAntwortEntwurf] = useState("");
  const [einstellungen, setEinstellungen] = useState<Einstellungen>({ sprache: "de", einfach: false });
  // Zählt Abläufe hoch; ein älterer Ablauf (Live oder Replay) schreibt nach einem neuen nichts mehr.
  const ablauf = useRef(0);

  const senden = useCallback(
    async (text: string, neu: boolean) => {
      const nummer = ++ablauf.current;
      const sitzung = neu ? undefined : verlauf.at(-1)?.antwort.sitzung_id;
      setAufnahme(null);
      if (neu) setVerlauf([]);
      setLage({ art: "laden" });
      const ergebnis = await frageSenden(text, sitzung, einstellungen);
      if (nummer !== ablauf.current) return;
      if ("meldung" in ergebnis) {
        setLage({ art: "fehler", meldung: ergebnis.meldung, replay: ergebnis.replay });
        return;
      }
      setVerlauf((alt) => [...(neu ? [] : alt), { eingabe: text.trim(), antwort: ergebnis.antwort }]);
      setAntwortEntwurf("");
      setLage({ art: "bereit" });
    },
    [verlauf, einstellungen],
  );

  const beispielAbspielen = useCallback(async () => {
    const nummer = ++ablauf.current;
    setVerlauf([]);
    setAntwortEntwurf("");
    setEntwurf("");
    setLage({ art: "laden" });
    const pruefung = await pruefeReplay(pflege);
    if (nummer !== ablauf.current) return;
    if (!pruefung.ok) {
      setAufnahme(null);
      setLage({
        art: "fehler",
        meldung:
          pruefung.grund === "hash"
            ? "Das aufgezeichnete Beispiel wurde verändert. Die Belege passen nicht mehr zur Aufnahme, deshalb zeigen wir es nicht."
            : "Das aufgezeichnete Beispiel ist unvollständig und wird nicht gezeigt.",
        replay: false,
      });
      return;
    }
    const { replay } = pruefung;
    setAufnahme(formatAufnahme(replay.aufgenommen));
    const erster = replay.schritte[0]?.eingabe;
    if (erster) setEinstellungen({ sprache: erster.sprache ?? "de", einfach: erster.stil === "einfach" });
    for (const [stelle, schritt] of replay.schritte.entries()) {
      if (stelle === 0) setEntwurf(schritt.eingabe.text);
      else setAntwortEntwurf(schritt.eingabe.text);
      setLage({ art: "laden" });
      await warte(REPLAY_PAUSE_MS);
      if (nummer !== ablauf.current) return;
      setVerlauf((alt) => [...alt, { eingabe: schritt.eingabe.text, antwort: schritt.antwort }]);
      setAntwortEntwurf("");
      setLage({ art: "bereit" });
      if (stelle < replay.schritte.length - 1) await warte(REPLAY_PAUSE_MS);
      if (nummer !== ablauf.current) return;
    }
  }, []);

  const wert = useMemo<LotseWert>(
    () => ({
      verlauf,
      lage,
      aufnahme,
      entwurf,
      setEntwurf,
      antwortEntwurf,
      setAntwortEntwurf,
      einstellungen,
      setEinstellungen,
      erzaehlen: (text) => senden(text, true),
      antworten: (text) => senden(text, false),
      beispielAbspielen,
    }),
    [verlauf, lage, aufnahme, entwurf, antwortEntwurf, einstellungen, senden, beispielAbspielen],
  );

  return <LotseKontext.Provider value={wert}>{children}</LotseKontext.Provider>;
}
