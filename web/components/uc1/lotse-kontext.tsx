"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { abbildenAntrag, antragEingabeSchema, webAntragSchema, type RohAntrag, type WebAntrag } from "./antrag";
import { frageSchema, webAntwortSchema, type WebAntwort } from "./antwort";
import { formatAufnahme, pruefeReplay } from "./replay";
import pflege from "./fixtures/pflege.json";

// Zustand des Lotsen für alle Seiten unter /uc1 (liegt im Layout, damit „Leistungen“, „Antrag“ und
// „Stelle“ nach dem Seitenwechsel dieselben Antworten zeigen). Die Sitzung lebt nur im React-Zustand.

export interface Wechsel {
  eingabe: string;
  antwort: WebAntwort;
}

/** Wo die Eingabe war, zu der ein Fehler gehört: dort steht er auch. */
export type FehlerOrt = "situation" | "rueckfrage";

export type Lage =
  | { art: "leer" }
  | { art: "laden" }
  | { art: "bereit" }
  | { art: "fehler"; meldung: string; replay: boolean; ort: FehlerOrt };

export type AntragLage =
  | { art: "leer" }
  | { art: "laden" }
  | { art: "bereit"; antraege: readonly WebAntrag[] }
  | { art: "fehler"; meldung: string; replay: boolean };

export interface Einstellungen {
  sprache: "de" | "en";
  einfach: boolean;
}

interface LotseWert {
  verlauf: readonly Wechsel[];
  lage: Lage;
  /** Gesetzt, solange eine Aufnahme statt einer Live-Antwort läuft oder zu sehen ist (Datum der Aufnahme). */
  aufnahme: string | null;
  /** Im Replay die Anträge, für die es eine Aufnahme gibt; live `null`. */
  aufgezeichnet: readonly string[] | null;
  /** Wahr, solange die Aufnahme abgespielt wird; Eingaben sind dann gesperrt. */
  spielt: boolean;
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
  /** Alles zurück auf Anfang (Knopf „Neue Situation“). */
  neuBeginnen: () => void;
  antrag: AntragLage;
  /** Bereitet die Anträge der letzten Antwort vor: live über /api/uc1/antrag, im Replay aus der Aufnahme. */
  antragVorbereiten: (arten: readonly string[]) => Promise<void>;
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

type Fehlschlag = { meldung: string; replay: boolean };

/** POST mit JSON; liefert die Daten oder einen deutschen Satz mit Replay-Angebot. */
async function senden(url: string, body: unknown, fallback: string): Promise<{ daten: unknown } | Fehlschlag> {
  let antwort: Response;
  try {
    antwort = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    return { meldung: "Keine Verbindung zum Server.", replay: true };
  }
  const daten: unknown = await antwort.json().catch(() => null);
  if (antwort.ok) return { daten };
  const feld = (name: string) =>
    daten && typeof daten === "object" && name in daten ? (daten as Record<string, unknown>)[name] : undefined;
  const meldung = typeof feld("fehler") === "string" ? (feld("fehler") as string) : fallback;
  // Sperrt ein Proxy POST (405) ohne JSON, gilt dasselbe wie in der Online-Demo.
  return { meldung, replay: feld("replay") === true || antwort.status === 405 };
}

async function frageSenden(
  text: string,
  sitzung: string | undefined,
  { sprache, einfach }: Einstellungen,
): Promise<{ antwort: WebAntwort } | Fehlschlag> {
  const eingabe = frageSchema.safeParse({ text, sitzung, stil: einfach ? "einfach" : "standard", sprache });
  if (!eingabe.success) {
    const meldung = eingabe.error.issues[0]?.message ?? "Die Eingabe ist ungültig.";
    // Die Meldung für ein leeres Feld passt nur zur Situation; bei einer Rückfrage fehlt eine Antwort.
    return { meldung: sitzung && !text.trim() ? "Bitte schreiben Sie eine kurze Antwort." : meldung, replay: false };
  }
  const ergebnis = await senden("/api/uc1/frage", eingabe.data, "Der Lotse hat nicht geantwortet.");
  if ("meldung" in ergebnis) return ergebnis;
  const geprueft = webAntwortSchema.safeParse(ergebnis.daten);
  return geprueft.success
    ? { antwort: geprueft.data }
    : { meldung: "Die Antwort kam in einem unerwarteten Format.", replay: true };
}

async function antragSenden(art: string, sitzung: string): Promise<{ antrag: WebAntrag } | Fehlschlag> {
  const eingabe = antragEingabeSchema.safeParse({ art, sitzung });
  if (!eingabe.success) return { meldung: "Für diesen Antrag fehlt die Sitzung. Bitte erzählen Sie die Situation neu.", replay: false };
  const ergebnis = await senden("/api/uc1/antrag", eingabe.data, "Der Antrag konnte nicht vorbereitet werden.");
  if ("meldung" in ergebnis) return ergebnis;
  const geprueft = webAntragSchema.safeParse(ergebnis.daten);
  return geprueft.success
    ? { antrag: geprueft.data }
    : { meldung: "Der Antrag kam in einem unerwarteten Format.", replay: true };
}

export function LotseAnbieter({ children }: { children: ReactNode }) {
  const [verlauf, setVerlauf] = useState<readonly Wechsel[]>([]);
  const [lage, setLage] = useState<Lage>({ art: "leer" });
  const [aufnahme, setAufnahme] = useState<string | null>(null);
  const [aufgezeichnet, setAufgezeichnet] = useState<readonly string[] | null>(null);
  const [spielt, setSpielt] = useState(false);
  const [entwurf, setEntwurf] = useState("");
  const [antwortEntwurf, setAntwortEntwurf] = useState("");
  const [einstellungen, setEinstellungen] = useState<Einstellungen>({ sprache: "de", einfach: false });
  const [antrag, setAntrag] = useState<AntragLage>({ art: "leer" });
  // Zählt Abläufe hoch; ein älterer Ablauf (Live oder Replay) schreibt nach einem neuen nichts mehr.
  const ablauf = useRef(0);
  // Rohe Antrag-Ausgabe der laufenden Aufnahme; im Replay kommt der Antrag von hier, nicht vom Server.
  const aufnahmeAntrag = useRef<RohAntrag | null>(null);

  const fragen = useCallback(
    async (text: string, neu: boolean) => {
      const nummer = ++ablauf.current;
      const sitzung = neu ? undefined : verlauf.at(-1)?.antwort.sitzung_id;
      setAufnahme(null);
      setAufgezeichnet(null);
      setSpielt(false);
      aufnahmeAntrag.current = null;
      if (neu) {
        setVerlauf([]);
        setAntrag({ art: "leer" });
      }
      setLage({ art: "laden" });
      const ergebnis = await frageSenden(text, sitzung, einstellungen);
      if (nummer !== ablauf.current) return;
      if ("meldung" in ergebnis) {
        setLage({ art: "fehler", meldung: ergebnis.meldung, replay: ergebnis.replay, ort: neu ? "situation" : "rueckfrage" });
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
    setAntrag({ art: "leer" });
    setLage({ art: "laden" });
    const pruefung = await pruefeReplay(pflege);
    if (nummer !== ablauf.current) return;
    if (!pruefung.ok) {
      setAufnahme(null);
      setAufgezeichnet(null);
      setSpielt(false);
      aufnahmeAntrag.current = null;
      setLage({
        art: "fehler",
        meldung:
          pruefung.grund === "hash"
            ? "Das aufgezeichnete Beispiel wurde verändert. Die Zitate passen nicht mehr zur Aufnahme, deshalb zeigen wir es nicht."
            : "Das aufgezeichnete Beispiel ist unvollständig und wird nicht gezeigt.",
        replay: false,
        ort: "situation",
      });
      return;
    }
    const { replay } = pruefung;
    aufnahmeAntrag.current = replay.antrag ?? null;
    setAufgezeichnet(replay.antrag ? [replay.antrag.art] : []);
    setAufnahme(formatAufnahme(replay.aufgenommen));
    setSpielt(true);
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
    setSpielt(false);
  }, []);

  const neuBeginnen = useCallback(() => {
    ++ablauf.current;
    aufnahmeAntrag.current = null;
    setVerlauf([]);
    setAufnahme(null);
    setAufgezeichnet(null);
    setSpielt(false);
    setEntwurf("");
    setAntwortEntwurf("");
    setAntrag({ art: "leer" });
    setLage({ art: "leer" });
  }, []);

  const antragVorbereiten = useCallback(
    async (arten: readonly string[]) => {
      const nummer = ablauf.current;
      const sitzung = verlauf.at(-1)?.antwort.sitzung_id ?? "";
      if (aufnahme !== null) {
        const roh = aufnahmeAntrag.current;
        const abgebildet = roh && arten.includes(roh.art) ? abbildenAntrag(roh) : null;
        setAntrag(
          abgebildet
            ? { art: "bereit", antraege: [abgebildet] }
            : { art: "fehler", meldung: "Für dieses Beispiel ist kein Antrag aufgezeichnet.", replay: false },
        );
        return;
      }
      setAntrag({ art: "laden" });
      const fertig: WebAntrag[] = [];
      // Nacheinander: die Route lässt höchstens zwei Läufe gleichzeitig zu.
      for (const art of arten) {
        const ergebnis = await antragSenden(art, sitzung);
        if (nummer !== ablauf.current) return;
        if ("meldung" in ergebnis) {
          setAntrag({ art: "fehler", meldung: ergebnis.meldung, replay: ergebnis.replay });
          return;
        }
        fertig.push(ergebnis.antrag);
      }
      setAntrag({ art: "bereit", antraege: fertig });
    },
    [verlauf, aufnahme],
  );

  const wert = useMemo<LotseWert>(
    () => ({
      verlauf,
      lage,
      aufnahme,
      aufgezeichnet,
      spielt,
      entwurf,
      setEntwurf,
      antwortEntwurf,
      setAntwortEntwurf,
      einstellungen,
      setEinstellungen,
      erzaehlen: (text) => fragen(text, true),
      antworten: (text) => fragen(text, false),
      beispielAbspielen,
      neuBeginnen,
      antrag,
      antragVorbereiten,
    }),
    [verlauf, lage, aufnahme, aufgezeichnet, spielt, entwurf, antwortEntwurf, einstellungen, fragen, beispielAbspielen, neuBeginnen, antrag, antragVorbereiten],
  );

  return <LotseKontext.Provider value={wert}>{children}</LotseKontext.Provider>;
}
