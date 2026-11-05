"use client";

import { useEffect, useRef, useState } from "react";
import { Knopf } from "../basis/knopf";
import { fokus, klassen } from "../basis/klassen";
import { Leerzustand } from "../basis/leerzustand";
import { Piktogramm } from "../basis/piktogramm";
import { Status } from "../basis/status";
import type { BereichId, UcEintrag } from "../ucs";
import { eintraegeSchema, type Eintrag } from "./eintrag";

// Protokoll-Schublade (Pen-Frame yK42X): 380 px, rechts, modal. Eine Liste: Uhrzeit in Mono, daneben Art und Wer,
// darunter was angewiesen wurde und was daraus wurde. Einträge von einem anderen Tag tragen das Datum unter der Uhrzeit. Sie setzt unter dem Header an (`oben`), damit Modell-Badge und Knopf „Protokoll“ sichtbar bleiben.
// Esc schließt. Den übrigen Inhalt macht die AppShell `inert` und gibt dem Knopf „Protokoll“ beim Schließen
// den Fokus zurück. Eine Antwort, die den Vertrag `Eintrag` verletzt, zeigt den Fehlerzustand statt halber Daten.

export interface ProtokollSchubladeProps {
  id: string;
  uc: UcEintrag;
  onSchliessen: () => void;
  /** Adresse der Einträge, Standard `/api/<uc>/protokoll`. */
  quelle?: (uc: BereichId) => string;
  /** Abstand vom oberen Fensterrand in px, meist die Unterkante des Headers. */
  oben?: number;
}

type Zustand = { art: "laden" } | { art: "ok"; eintraege: Eintrag[] } | { art: "fehler" };

const standardQuelle = (uc: BereichId) => `/api/${uc}/protokoll`;

const datum = new Intl.DateTimeFormat("de-AT", { timeZone: "Europe/Vienna", day: "2-digit", month: "2-digit" });
const uhrzeit = new Intl.DateTimeFormat("de-AT", { timeZone: "Europe/Vienna", hour: "2-digit", minute: "2-digit" });
const voll = new Intl.DateTimeFormat("de-AT", { timeZone: "Europe/Vienna", dateStyle: "long", timeStyle: "medium" });

/** Art des Eintrags, wie der Frame sie nennt: der Status des Eintrags und wer ihn schrieb ergeben das Wort. */
function art(eintrag: Eintrag): { wort: string; klasse: string } {
  if (eintrag.status === "freigegeben") return { wort: "Freigabe", klasse: "text-gruen" };
  if (eintrag.status === "abgelehnt") return { wort: "Ablehnung", klasse: "text-err-fg" };
  return { wort: eintrag.akteur === "agent" ? "Vorschlag" : "Anweisung", klasse: "text-ink" };
}

function Zeile({ eintrag, heute }: { eintrag: Eintrag; heute: string }) {
  const zeit = new Date(eintrag.zeit);
  const tag = datum.format(zeit);
  const { wort, klasse } = art(eintrag);
  return (
    <li
      className="flex gap-3 border-b border-line py-3 font-sans text-13"
      data-status={eintrag.status}
      data-akteur={eintrag.akteur}
    >
      <time
        dateTime={eintrag.zeit}
        title={voll.format(zeit)}
        className="flex w-10 shrink-0 flex-col font-mono text-12 tabular-nums text-slate"
      >
        <span>{uhrzeit.format(zeit)}</span>
        {tag !== heute && <span>{tag}</span>}
      </time>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <p className="flex flex-wrap items-center gap-x-1.5">
          <span className={klassen("font-bold", klasse)}>{wort}</span>
          <span className="break-words text-slate">{`· ${eintrag.name}`}</span>
        </p>
        <p className="break-words text-ink">{eintrag.anweisung}</p>
        {eintrag.wirkung && <p className="break-words text-slate">{eintrag.wirkung}</p>}
      </div>
    </li>
  );
}

export function ProtokollSchublade({ id, uc, onSchliessen, quelle = standardQuelle, oben = 0 }: ProtokollSchubladeProps) {
  const [zustand, setZustand] = useState<Zustand>({ art: "laden" });
  const [versuch, setVersuch] = useState(0);
  const titel = useRef<HTMLHeadingElement>(null);
  const adresse = quelle(uc.id);

  // Fokus in die Schublade, auf die Überschrift, nie auf eine Aktion. Die Rückgabe macht die AppShell per Ref.
  useEffect(() => {
    titel.current?.focus();
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

  const heute = datum.format(new Date());
  return (
    <div
      id={id}
      role="dialog"
      aria-modal="true"
      aria-label={`Protokoll ${uc.name}`}
      style={{ top: oben }}
      className="fixed bottom-0 right-0 z-50 flex w-95 max-w-full flex-col border-l border-t border-line bg-white"
    >
      <div className="flex items-center gap-2 border-b border-line px-5 py-4">
        <Piktogramm name="protokoll" groesse={18} className="shrink-0 text-ink" />
        <h2
          ref={titel}
          tabIndex={-1}
          className={klassen("flex-1 font-display text-20 font-bold text-ink", fokus)}
        >
          Protokoll
        </h2>
        <button
          type="button"
          aria-label="Schließen"
          onClick={onSchliessen}
          className={klassen("inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-slate hover:bg-paper", fokus)}
        >
          <Piktogramm name="schliessen" groesse={18} />
        </button>
      </div>
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-5 py-2">
        {zustand.art === "laden" && (
          <p role="status" className="py-2 font-sans text-14 text-slate">
            Protokoll wird geladen.
          </p>
        )}
        {zustand.art === "fehler" && (
          <div role="alert" className="flex flex-col items-start gap-4 py-2">
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
          <ol aria-label={`Protokoll ${uc.name}, neueste zuerst`} className="flex flex-col">
            {zustand.eintraege.map((eintrag) => (
              <Zeile key={eintrag.id} eintrag={eintrag} heute={heute} />
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
