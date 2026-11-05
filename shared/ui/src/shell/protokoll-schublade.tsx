"use client";

import { useEffect, useRef, useState } from "react";
import { Knopf } from "../basis/knopf";
import { fokus, klassen } from "../basis/klassen";
import { Leerzustand } from "../basis/leerzustand";
import { Status } from "../basis/status";
import type { UcEintrag, UcId } from "../ucs";
import { eintraegeSchema, type Eintrag } from "./eintrag";

// Protokoll-Schublade (Pen-Frame yK42X): 380 px, rechts, nicht modal. Zeigt, wer was angewiesen hat und was
// daraus wurde. Esc schließt, der Fokus kehrt zum auslösenden Element zurück. Eine Antwort, die den Vertrag
// `Eintrag` verletzt, zeigt den Fehlerzustand statt halber Daten.

export interface ProtokollSchubladeProps {
  id: string;
  uc: UcEintrag;
  onSchliessen: () => void;
  /** Adresse der Einträge, Standard `/api/<uc>/protokoll`. */
  quelle?: (uc: UcId) => string;
}

type Zustand = { art: "laden" } | { art: "ok"; eintraege: Eintrag[] } | { art: "fehler" };

const standardQuelle = (uc: UcId) => `/api/${uc}/protokoll`;

const datum = new Intl.DateTimeFormat("de-AT", { timeZone: "Europe/Vienna", day: "2-digit", month: "2-digit" });
const uhrzeit = new Intl.DateTimeFormat("de-AT", { timeZone: "Europe/Vienna", hour: "2-digit", minute: "2-digit" });
const voll = new Intl.DateTimeFormat("de-AT", { timeZone: "Europe/Vienna", dateStyle: "long", timeStyle: "medium" });

function StatusWort({ status }: { status: Eintrag["status"] }) {
  if (status === "freigegeben") return <Status art="ok">Freigegeben</Status>;
  if (status === "abgelehnt") return <Status art="fehler">Abgelehnt</Status>;
  return <Status art="info">Wartet auf Freigabe</Status>;
}

function Zeile({ eintrag }: { eintrag: Eintrag }) {
  const zeit = new Date(eintrag.zeit);
  return (
    <tr className="border-b border-line align-top" data-status={eintrag.status}>
      <td className="py-2 pr-2 font-mono tabular-nums text-slate">
        <time dateTime={eintrag.zeit} title={voll.format(zeit)} className="flex flex-col">
          <span>{datum.format(zeit)}</span>
          <span>{uhrzeit.format(zeit)}</span>
        </time>
      </td>
      <td className="py-2 pr-2 text-ink">
        {eintrag.akteur === "agent" ? <span className="border-l-2 border-violett pl-1">Agent</span> : "Mensch"}
      </td>
      <td className="py-2 pr-2 break-words text-ink">{eintrag.name}</td>
      <td className="py-2">
        <div className="flex flex-col items-start gap-1">
          <span className="text-ink">{eintrag.anweisung}</span>
          {eintrag.wirkung && <span className="text-slate">{eintrag.wirkung}</span>}
          <StatusWort status={eintrag.status} />
        </div>
      </td>
    </tr>
  );
}

function Zusammenfassung({ eintraege }: { eintraege: Eintrag[] }) {
  const offen = eintraege.filter((e) => e.status === "offen").length;
  const anzahl = eintraege.length === 1 ? "1 Eintrag" : `${eintraege.length} Einträge`;
  const warten = offen === 0 ? "nichts wartet auf Freigabe" : `${offen} ${offen === 1 ? "wartet" : "warten"} auf Freigabe`;
  return <p className="font-sans text-14 text-ink">{`${anzahl}, ${warten}.`}</p>;
}

export function ProtokollSchublade({ id, uc, onSchliessen, quelle = standardQuelle }: ProtokollSchubladeProps) {
  const [zustand, setZustand] = useState<Zustand>({ art: "laden" });
  const [versuch, setVersuch] = useState(0);
  const titel = useRef<HTMLHeadingElement>(null);
  const adresse = quelle(uc.id);

  // Fokus in die Schublade (auf die Überschrift, nie auf eine Aktion) und beim Schließen zurück.
  useEffect(() => {
    const vorher = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    titel.current?.focus();
    return () => vorher?.focus();
  }, []);

  useEffect(() => {
    const beiTaste = (ereignis: KeyboardEvent) => {
      if (ereignis.key === "Escape") onSchliessen();
    };
    document.addEventListener("keydown", beiTaste);
    return () => document.removeEventListener("keydown", beiTaste);
  }, [onSchliessen]);

  useEffect(() => {
    const abbruch = new AbortController();
    setZustand({ art: "laden" });
    fetch(adresse, { signal: abbruch.signal, cache: "no-store" })
      .then(async (antwort) => {
        const geprueft = eintraegeSchema.safeParse(antwort.ok ? await antwort.json() : null);
        if (abbruch.signal.aborted) return;
        setZustand(geprueft.success ? { art: "ok", eintraege: geprueft.data } : { art: "fehler" });
      })
      .catch(() => {
        if (!abbruch.signal.aborted) setZustand({ art: "fehler" });
      });
    return () => abbruch.abort();
  }, [adresse, versuch]);

  const titelId = `${id}-titel`;
  return (
    <aside
      id={id}
      role="dialog"
      aria-modal="false"
      aria-labelledby={titelId}
      className="fixed inset-y-0 right-0 z-50 flex w-[380px] max-w-full flex-col border-l border-line bg-white"
    >
      <div className="flex items-start justify-between gap-4 border-b border-line p-4">
        <div className="flex flex-col gap-1">
          <h2
            ref={titel}
            id={titelId}
            tabIndex={-1}
            className={klassen("font-display text-20 font-bold text-ink", fokus)}
          >
            {`Protokoll ${uc.name}`}
          </h2>
          <p className="font-sans text-14 text-slate">Wer hat was angewiesen, und was ist daraus geworden.</p>
        </div>
        <Knopf art="sekundaer" onClick={onSchliessen}>
          Schließen
        </Knopf>
      </div>
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
        {zustand.art === "laden" && (
          <p role="status" className="font-sans text-14 text-slate">
            Protokoll wird geladen.
          </p>
        )}
        {zustand.art === "fehler" && (
          <div role="alert" className="flex flex-col items-start gap-4">
            <Status art="fehler">Protokoll nicht erreichbar</Status>
            <p className="font-sans text-14 text-slate">Die Einträge kamen nicht oder nicht im erwarteten Format.</p>
            <Knopf art="sekundaer" onClick={() => setVersuch((v) => v + 1)}>
              Erneut laden
            </Knopf>
          </div>
        )}
        {zustand.art === "ok" && zustand.eintraege.length === 0 && (
          <Leerzustand satz={`Für ${uc.name} gibt es noch keine Einträge.`} className="py-0" />
        )}
        {zustand.art === "ok" && zustand.eintraege.length > 0 && (
          <>
            <Zusammenfassung eintraege={zustand.eintraege} />
            <table className="w-full table-fixed border-collapse text-left font-sans text-12">
              <caption className="sr-only">{`Protokoll ${uc.name}, neueste zuerst`}</caption>
              <colgroup>
                <col className="w-14" />
                <col className="w-16" />
                <col className="w-24" />
                <col />
              </colgroup>
              <thead>
                <tr className="border-b border-line text-slate">
                  <th scope="col" className="py-2 pr-2 font-medium">Zeit</th>
                  <th scope="col" className="py-2 pr-2 font-medium">Art</th>
                  <th scope="col" className="py-2 pr-2 font-medium">Wer</th>
                  <th scope="col" className="py-2 font-medium">Was</th>
                </tr>
              </thead>
              <tbody>
                {zustand.eintraege.map((eintrag) => (
                  <Zeile key={eintrag.id} eintrag={eintrag} />
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </aside>
  );
}
