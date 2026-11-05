"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { EREIGNIS_ARTEN } from "../typen";
import { ableiten, type FallZustand } from "../zustand";
import type { Verbindung } from "../use-ereignisstrom";
import { taktMs, type RohEreignis } from "./takt";

// Liest den Ereignisstrom eines Falls (SSE) in eine Liste und spielt sie im Lesetakt ab. Der Zustand entsteht immer
// aus den bisher gezeigten Ereignissen (ableiten), so sieht Live, Aufzeichnung und Wiederholung gleich aus.

export interface Wiedergabe {
  /** Zustand aus allen bisher gezeigten Ereignissen. */
  zustand: FallZustand;
  /** Zustand aus allem, was angekommen ist (für "Zum Ergebnis"). */
  gesamt: FallZustand;
  gezeigt: RohEreignis[];
  verbindung: Verbindung;
  pausiert: boolean;
  tempo: number;
  /** Anteil der gezeigten Ereignisse, 0 bis 1, für den Fortschritt. */
  anteil: number;
  umschalten: () => void;
  setTempo: (t: number) => void;
  weiter: () => void;
  zumEnde: () => void;
  vonVorn: () => void;
  neuVerbinden: () => void;
}

function istRoh(d: unknown): d is RohEreignis & Record<string, unknown> {
  return typeof d === "object" && d !== null && typeof (d as { seq?: unknown }).seq === "number" && typeof (d as { art?: unknown }).art === "string";
}

export function useWiedergabe(fallId: string): Wiedergabe {
  const [ereignisse, setEreignisse] = useState<(RohEreignis & Record<string, unknown>)[]>([]);
  const [verbindung, setVerbindung] = useState<Verbindung>("verbindet");
  const [versuch, setVersuch] = useState(0);
  const [index, setIndex] = useState(0);
  const [pausiert, setPausiert] = useState(false);
  const [tempo, setTempo] = useState(1);
  const letzte = useRef(0);

  useEffect(() => {
    if (typeof EventSource === "undefined") {
      setVerbindung("unterbrochen");
      return;
    }
    setVerbindung("verbindet");
    const ab = letzte.current > 0 ? `?seq=${letzte.current}` : "";
    const quelle = new EventSource(`/api/uc2/faelle/${encodeURIComponent(fallId)}/ereignisse${ab}`);
    quelle.onopen = () => setVerbindung("offen");
    quelle.onerror = () => {
      if (quelle.readyState !== EventSource.CLOSED) {
        setVerbindung("verbindet");
        return;
      }
      if (letzte.current > 0) {
        setVerbindung("unterbrochen");
        return;
      }
      fetch(`/api/uc2/faelle/${encodeURIComponent(fallId)}`, { cache: "no-store" })
        .then((antwort) => setVerbindung(antwort.status === 404 ? "nicht-gefunden" : "unterbrochen"))
        .catch(() => setVerbindung("unterbrochen"));
    };
    const hoeren = (art: string) => (ereignis: Event) => {
      let daten: unknown;
      try {
        daten = JSON.parse((ereignis as MessageEvent<string>).data);
      } catch {
        return;
      }
      if (art === "ende") {
        const status = (daten as { status?: unknown } | null)?.status;
        setEreignisse((liste) => [...liste, { seq: letzte.current + 1, art: "ende", daten: { status } }]);
        setVerbindung("zu");
        quelle.close();
        return;
      }
      if (!istRoh(daten)) return;
      const seq = daten.seq;
      if (seq <= letzte.current) return;
      letzte.current = seq;
      setEreignisse((liste) => [...liste, daten]);
    };
    for (const art of EREIGNIS_ARTEN) quelle.addEventListener(art, hoeren(art));
    return () => quelle.close();
  }, [fallId, versuch]);

  const listeRef = useRef(ereignisse);
  listeRef.current = ereignisse;
  const mehr = index < ereignisse.length;

  // Takt: nach einem Ereignis mit eigener Bühne warten, Ereignisse ohne Bühne sofort mitnehmen.
  useEffect(() => {
    // Neue Ereignisse dürfen den laufenden Takt nicht neu starten (sie kommen alle 150 ms); darum liest der Timer die
    // Liste über eine Referenz und hängt nur davon ab, ob überhaupt etwas Neues da ist.
    if (pausiert || !mehr) return;
    const liste = listeRef.current;
    const warten = index === 0 ? 0 : taktMs(liste[index - 1]?.art, tempo);
    const uhr = setTimeout(() => {
      const jetzt = listeRef.current;
      let naechster = index + 1;
      while (naechster < jetzt.length && taktMs(jetzt[naechster - 1]?.art, 1) === 0) naechster++;
      setIndex(Math.min(naechster, jetzt.length));
    }, warten);
    return () => clearTimeout(uhr);
  }, [index, mehr, pausiert, tempo]);

  const gezeigt = useMemo(() => ereignisse.slice(0, index), [ereignisse, index]);
  const zustand = useMemo(() => ableiten(gezeigt), [gezeigt]);
  const gesamt = useMemo(() => ableiten(ereignisse), [ereignisse]);

  return {
    zustand,
    gesamt,
    gezeigt,
    verbindung,
    pausiert,
    tempo,
    anteil: ereignisse.length === 0 ? 0 : index / ereignisse.length,
    umschalten: () => setPausiert((p) => !p),
    setTempo,
    weiter: () => {
      let naechster = index + 1;
      while (naechster < ereignisse.length && taktMs(ereignisse[naechster - 1]?.art, 1) === 0) naechster++;
      setIndex(Math.min(naechster, ereignisse.length));
    },
    zumEnde: () => setIndex(ereignisse.length),
    vonVorn: () => {
      setIndex(0);
      setPausiert(false);
    },
    neuVerbinden: () => setVersuch((v) => v + 1),
  };
}
