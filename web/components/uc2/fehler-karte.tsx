"use client";

import { Fliesstext, Knopf, Status } from "@kic/ui/basis";
import type { ModellWahl } from "../../app/api/uc2/_lib/vorbereitung";
import { klartext } from "./namen";
import type { FallZustand } from "./zustand";

// U2-1a Modellfehler inline (Pen NjP7Q): rotes Band über den Runden. Die fertigen Runden bleiben stehen. "Erneut
// versuchen" startet den Fall mit demselben Modell neu, ein Modellwechsel mit einem der anderen. Ein Modell, das hier
// nicht eingerichtet ist (ollama), zeigt statt des Knopfs eine sichtbare Meldung.

/** Der Fehlertyp aus dem Ereignis `abbruch` als Satz für Bürger. Unbekannte Typen bekommen einen neutralen Satz. */
export function grundSatz(grund: string | null | undefined, modell: string | null): string {
  const m = modell ? `Das Modell ${modell}` : "Das Modell";
  const g = (grund ?? "").toLowerCase();
  if (/timeout|zeit/.test(g)) return `${m} hat nicht rechtzeitig geantwortet.`;
  if (/connect|network|netz|unavailable|nicht.?erreich|dns/.test(g)) return `${m} war nicht erreichbar.`;
  if (/ratelimit|rate_limit|429|quota|toomany/.test(g)) return `${m} hatte zu viele Anfragen und hat gebremst.`;
  if (/auth|permission|forbidden|401|403|key/.test(g)) return `Die Anmeldung beim Modell ${modell ?? ""} hat nicht geklappt.`.replace("  ", " ");
  return `${m} hat einen Fehler gemeldet.`;
}

export function fertigeRunden(zustand: FallZustand): number[] {
  return zustand.runden.filter((r) => r.ende).map((r) => r.nr);
}

function rundenSatz(nr: number[]): string {
  if (nr.length === 0) return "Es gab noch keine fertige Runde.";
  if (nr.length === 1) return `Runde ${nr[0]} ist fertig und bleibt stehen.`;
  const klein = nr[0];
  const gross = nr.at(-1);
  return nr.length === 2
    ? `Die Runden ${klein} und ${gross} sind fertig und bleiben stehen.`
    : `Die Runden ${klein} bis ${gross} sind fertig und bleiben stehen.`;
}

export function FehlerKarte({
  zustand,
  modelle,
  laedt,
  meldung,
  onNeu,
}: {
  zustand: FallZustand;
  modelle: ModellWahl[];
  laedt: boolean;
  meldung: string | null;
  onNeu: (provider: ModellWahl["id"] | null) => void;
}) {
  const f = zustand.fehler;
  const aktuell = zustand.provider ?? zustand.modelle?.akteur?.provider ?? null;
  const runde = f?.runde ?? zustand.runden.at(-1)?.nr ?? null;
  const andere = modelle.filter((m) => m.id !== aktuell);

  return (
    <div className="flex flex-col gap-4 border-y border-err-fg bg-err-bg px-4 py-4" role="alert" data-zustand="modellfehler">
      <div className="flex flex-col gap-1">
        <Status art="fehler">{runde ? `Runde ${runde} ist abgebrochen` : "Die Verhandlung ist abgebrochen"}</Status>
        <Fliesstext data-teil="fehlertext">
          {`${grundSatz(f?.grund, aktuell)}${f?.meldung ? ` ${f.meldung.replace(/\.$/, "").replace(/\b(\d+)\s?s\b/g, "$1 Sekunden")}.` : ""} ${rundenSatz(fertigeRunden(zustand))}`}
        </Fliesstext>
        <Fliesstext groesse={14} ton="gedaempft">
          Ein neuer Versuch beginnt wieder bei Runde 1. Die Runden hier bleiben zum Nachlesen stehen.
        </Fliesstext>
        {f?.grund && (
          <p className="font-mono text-12 text-slate" data-teil="grund">{`Technischer Grund: ${f.grund}`}</p>
        )}
      </div>
      <div className="flex flex-wrap items-start gap-3">
        <Knopf onClick={() => onNeu(null)} disabled={laedt} data-testid="uc2-erneut">
          Erneut versuchen
        </Knopf>
        {andere.map((m) => (
          <div key={m.id} className="flex flex-col items-start gap-1" data-modell={m.id}>
            <Knopf art="sekundaer" onClick={() => onNeu(m.id)} disabled={laedt || !m.verfuegbar} data-testid={`uc2-modell-${m.id}`}>
              {`Modell wechseln: ${m.label}`}
            </Knopf>
            {!m.verfuegbar && m.meldung && <p className="max-w-xs font-sans text-12 text-slate">{m.meldung}</p>}
          </div>
        ))}
      </div>
      {meldung && <Status art="fehler">{meldung}</Status>}
    </div>
  );
}
