"use client";

import { useEffect, useRef, useState } from "react";
import { Knopf } from "../basis/knopf";
import { fokus, klassen } from "../basis/klassen";
import { Leerzustand } from "../basis/leerzustand";
import { Piktogramm } from "../basis/piktogramm";
import { Status, type StatusArt } from "../basis/status";
import type { BereichId, UcEintrag } from "../ucs";
import { eintraegeSchema, type Eintrag } from "./eintrag";

// Protokoll-Schublade (Pen-Frame yK42X): 380 px, rechts, modal. Eine Liste: Uhrzeit in Mono, daneben Art und Wer,
// darunter was angewiesen wurde und was daraus wurde. Einträge von einem anderen Tag tragen das Datum unter der
// Uhrzeit. Sie setzt unter dem Header an (`oben`), damit Modell-Badge und Knopf „Protokoll“ sichtbar bleiben.
// Die Art kommt nur aus `akteur` (Vorschlag eines Agenten, Anweisung eines Menschen); der Status steht getrennt
// daneben. So steht nie „Freigabe · regel-agent“: freigeben kann nur ein Mensch.
// Esc schließt, Tab und Umschalt+Tab laufen innerhalb der Schublade um. Den übrigen Inhalt macht die AppShell
// `inert` und gibt dem Knopf „Protokoll“ beim Schließen den Fokus zurück. Eine Antwort, die den Vertrag `Eintrag` verletzt, zeigt den Fehlerzustand statt halber Daten.

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
/** Kalendertag mit Jahr: „heute“ ist derselbe Tag im selben Jahr, nicht nur derselbe Tag und Monat. */
const kalendertag = new Intl.DateTimeFormat("de-AT", { timeZone: "Europe/Vienna", dateStyle: "short" });
const uhrzeit = new Intl.DateTimeFormat("de-AT", { timeZone: "Europe/Vienna", hour: "2-digit", minute: "2-digit" });
const voll = new Intl.DateTimeFormat("de-AT", { timeZone: "Europe/Vienna", dateStyle: "long", timeStyle: "medium" });

/** Art des Eintrags: nur wer ihn schrieb. Ob er freigegeben ist, zeigt der Status daneben. */
function art(eintrag: Eintrag): string {
  return eintrag.akteur === "agent" ? "Vorschlag" : "Anweisung";
}

const statusAnzeige: Record<Eintrag["status"], { art: StatusArt; wort: string }> = {
  offen: { art: "info", wort: "offen" },
  freigegeben: { art: "ok", wort: "freigegeben" },
  abgelehnt: { art: "fehler", wort: "abgelehnt" },
};

const FOKUSSIERBAR = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function Zeile({ eintrag, heute }: { eintrag: Eintrag; heute: string }) {
  const zeit = new Date(eintrag.zeit);
  const status = statusAnzeige[eintrag.status];
  return (
    <li
      className="flex gap-3 border-b border-line py-3 font-sans text-13"
      data-status={eintrag.status}
      data-akteur={eintrag.akteur}
    >
      <time
        dateTime={eintrag.zeit}
        title={voll.format(zeit)}
        className="flex w-11 shrink-0 flex-col font-mono text-12 tabular-nums text-slate"
      >
        <span>{uhrzeit.format(zeit)}</span>
        {kalendertag.format(zeit) !== heute && <span>{datum.format(zeit)}</span>}
      </time>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <p className="flex flex-wrap items-center gap-x-1.5">
          <span className="font-bold text-ink" data-art="">
            {art(eintrag)}
          </span>
          <span className="break-words text-slate">{`· ${eintrag.name}`}</span>
          <Status art={status.art} klein className="ml-1" data-eintrag-status="">
            {status.wort}
          </Status>
        </p>
        <p className="break-words text-ink">{eintrag.anweisung}</p>
        {eintrag.wirkung && <p className="whitespace-pre-line break-words text-slate">{eintrag.wirkung}</p>}
      </div>
    </li>
  );
}

export function ProtokollSchublade({ id, uc, onSchliessen, quelle = standardQuelle, oben = 0 }: ProtokollSchubladeProps) {
  const [zustand, setZustand] = useState<Zustand>({ art: "laden" });
  const [versuch, setVersuch] = useState(0);
  const titel = useRef<HTMLHeadingElement>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const adresse = quelle(uc.id);

  // Fokus in die Schublade, auf die Überschrift, nie auf eine Aktion. Die Rückgabe macht die AppShell per Ref.
  useEffect(() => {
    titel.current?.focus();
  }, []);

  useEffect(() => {
    const beiTaste = (ereignis: KeyboardEvent) => {
      if (ereignis.key === "Escape") {
        onSchliessen();
        return;
      }
      if (ereignis.key !== "Tab" || !dialog.current) return;
      // Fokusfalle: vom letzten Element zum ersten und zurück; Fokus außerhalb kommt zurück in die Schublade.
      const ziele = Array.from(dialog.current.querySelectorAll<HTMLElement>(FOKUSSIERBAR));
      const erstes = ziele[0];
      const letztes = ziele[ziele.length - 1];
      if (!erstes || !letztes) {
        ereignis.preventDefault();
        titel.current?.focus();
        return;
      }
      const aktiv = document.activeElement;
      const drinnen = aktiv instanceof HTMLElement && ziele.includes(aktiv);
      if (ereignis.shiftKey && (aktiv === erstes || !drinnen)) {
        ereignis.preventDefault();
        letztes.focus();
      } else if (!ereignis.shiftKey && (aktiv === letztes || !drinnen)) {
        ereignis.preventDefault();
        erstes.focus();
      }
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

  const heute = kalendertag.format(new Date());
  return (
    <div
      id={id}
      ref={dialog}
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
          className="flex-1 font-display text-20 font-bold text-ink outline-none"
        >
          Protokoll
        </h2>
        <button
          type="button"
          aria-label="Schließen"
          onClick={onSchliessen}
          className={klassen("inline-flex size-11 shrink-0 items-center justify-center rounded-lg text-slate hover:bg-paper", fokus)}
        >
          <Piktogramm name="schliessen" groesse={18} />
        </button>
      </div>
      {/* Scrollbereich in der Fokusliste der Fokusfalle: mit Tab erreichbar, Pfeil und Bild-ab scrollen (Review !45). */}
      <div
        tabIndex={0}
        role="region"
        aria-label="Protokoll-Einträge"
        className={klassen("flex flex-1 flex-col gap-4 overflow-y-auto px-5 py-2", fokus)}
      >
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
