import { Fliesstext, Knopf, Status, Ueberschrift } from "@kic/ui/basis";
import { Begriff } from "@kic/ui/bausteine";
import type { ReactNode } from "react";
import type { ModellWahl } from "../../app/api/uc2/_lib/vorbereitung";
import { ExperteSpur } from "./experte-spur";
import { FehlerKarte } from "./fehler-karte";
import { klartext, akteurName, THEMEN } from "./namen";
import { ModeratorSpur } from "./moderator-spur";
import { PersonaSpur } from "./persona-spur";
import { Stand } from "./stand";
import type { Verbindung } from "./use-ereignisstrom";
import { Verlauf } from "./verlauf";
import { aktuelleRunde, type FallZustand } from "./zustand";
import { Schritte } from "./schritte";

// U2-1 Das Panel verhandelt (Pen f1ct2) und U2-1a Modellfehler (Pen NjP7Q), als reine Ansicht auf einen Zustand.
// Reihenfolge, damit der Blick geführt wird: Titel und Schritt, wer spricht, was gilt (Stand), die Personas links,
// rechts Moderator und Experte, unten der Verlauf. Alle Zustände: wartet, läuft, fertig, abgebrochen, Verbindung weg.

export function titelText(z: FallZustand): string {
  const runde = aktuelleRunde(z);
  if (z.status === "fertig") return `Das Panel ist nach ${z.ergebnis?.runden ?? runde} Runden fertig`;
  if (z.status === "abgebrochen") return runde > 0 ? `Die Verhandlung ist in Runde ${runde} abgebrochen` : "Die Verhandlung ist abgebrochen";
  if (z.status === "wartet" || runde === 0) return z.status === "wartet" ? "Das Panel wird vorbereitet" : "Das Panel startet";
  return `Das Panel verhandelt, Runde ${runde}${z.maxRunden ? ` von höchstens ${z.maxRunden}` : ""}`;
}

export function sprecherText(z: FallZustand): string {
  if (z.status !== "laeuft") return "";
  if (z.sprecher === "moderator") return "Der Moderator fasst die Runde zusammen.";
  if (z.sprecher) return `Gerade spricht: ${akteurName(z.sprecher)}`;
  const runde = aktuelleRunde(z);
  return runde > 0 ? `Runde ${runde} ist beraten. Die nächste beginnt gleich.` : "Der Moderator wählt, wer am Tisch sitzt.";
}

function StatusChip({ z }: { z: FallZustand }) {
  const runde = aktuelleRunde(z);
  if (z.status === "fertig") return <Status art="ok">Fertig</Status>;
  if (z.status === "abgebrochen") return <Status art="fehler">Abgebrochen</Status>;
  return <Status art="info">{runde > 0 ? `Läuft · Runde ${runde}` : "Läuft"}</Status>;
}

export interface PanelAnsichtProps {
  zustand: FallZustand;
  verbindung: Verbindung;
  fallId: string;
  modelle: ModellWahl[];
  neuLaedt?: boolean;
  neuMeldung?: string | null;
  onNeu?: (provider: ModellWahl["id"] | null) => void;
  onNeuVerbinden?: () => void;
  /** Die API hat die Auswahl der Gruppen von U2-0 abgelehnt; der Moderator hat selbst gewählt. */
  akteureIgnoriert?: boolean;
}

export function PanelAnsicht({ zustand, verbindung, fallId, modelle, neuLaedt = false, neuMeldung = null, onNeu, onNeuVerbinden, akteureIgnoriert = false }: PanelAnsichtProps): ReactNode {
  const aktiverSchritt = zustand.status === "fertig" ? 3 : 2;
  const aufgezeichnet = fallId.startsWith("mock-");
  const verloren = verbindung === "unterbrochen" && zustand.status !== "fertig" && zustand.status !== "abgebrochen";
  const modell = zustand.modelle?.akteur;

  return (
    <div className="flex flex-col gap-6" data-fall={fallId} data-status={zustand.status}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex max-w-3xl flex-col gap-2">
          <Ueberschrift stufe={2} als="h1" data-testid="uc2-titel">
            {titelText(zustand)}
          </Ueberschrift>
          {zustand.frage && (
            <Fliesstext ton="gedaempft" data-testid="uc2-frage">
              {klartext(zustand.frage)}
            </Fliesstext>
          )}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            {modell && (
              <p className="inline-flex items-center gap-2 border-l-2 border-violett pl-2 font-sans text-12" data-testid="uc2-modell">
                <span className="text-slate">Modell</span>
                <span className="font-mono text-ink">{[modell.provider, modell.modell].filter(Boolean).join(" · ")}</span>
              </p>
            )}
            {aufgezeichnet && <Status art="info">Aufgezeichnete Verhandlung, ohne Sprachmodell</Status>}
            {akteureIgnoriert && (
              <Status art="info" data-testid="uc2-akteure-hinweis">
                Deine Auswahl der Gruppen wurde nicht übernommen. Der Moderator hat selbst gewählt.
              </Status>
            )}
          </div>
        </div>
        <StatusChip z={zustand} />
      </div>

      <Schritte aktiv={aktiverSchritt} />

      <p role="status" className="min-h-6 font-sans text-16 font-semibold text-ink" data-testid="uc2-sprecher">
        {sprecherText(zustand)}
      </p>

      {zustand.status === "abgebrochen" && onNeu && (
        <FehlerKarte zustand={zustand} modelle={modelle} laedt={neuLaedt} meldung={neuMeldung} onNeu={onNeu} />
      )}

      {verloren && (
        <div className="flex flex-wrap items-center gap-3" role="alert">
          <Status art="warnung">Die Verbindung zum Panel ist abgebrochen. Was schon da ist, bleibt stehen.</Status>
          {onNeuVerbinden && (
            <Knopf art="sekundaer" onClick={onNeuVerbinden}>
              Neu verbinden
            </Knopf>
          )}
        </div>
      )}
      {verbindung === "verbindet" && zustand.status === "laeuft" && zustand.letzteSeq > 0 && (
        <Status art="info">Die Verbindung wird neu aufgebaut.</Status>
      )}

      <Stand zustand={zustand} />

      <div className="grid gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-6">
          <section className="flex flex-col gap-3" aria-labelledby="uc2-positionen" data-spur="personas">
            <Ueberschrift stufe={3} als="h2" id="uc2-positionen">
              Positionen
            </Ueberschrift>
            {zustand.teilnehmer.length === 0 ? (
              <Fliesstext ton="gedaempft" data-testid="uc2-leer">
                {zustand.status === "abgebrochen"
                  ? "Es wurde noch niemand gehört."
                  : "Der Moderator wählt gerade, wer am Tisch sitzt. Gleich geht es los."}
              </Fliesstext>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {zustand.teilnehmer.map((a) => (
                  <PersonaSpur key={a} zustand={zustand} akteur={a} />
                ))}
              </div>
            )}
          </section>

          {zustand.themen.length > 0 && (
            <section className="flex flex-col gap-3 border-t border-line pt-6" aria-labelledby="uc2-themen" data-spur="themen">
              <Ueberschrift stufe={3} als="h2" id="uc2-themen">
                Worum es geht
              </Ueberschrift>
              <ul className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                {zustand.themen.map((t) => (
                  <li key={t.id} className="font-sans text-14 font-semibold text-ink">
                    <Begriff
                      wort={THEMEN[t.id]?.kurz ?? t.titel}
                      erklaerung={THEMEN[t.id]?.erklaerung ?? klartext(t.beschreibung ?? t.titel)}
                      untertitel
                    />
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        <div className="flex min-w-0 flex-col gap-8 lg:self-start">
          <ModeratorSpur zustand={zustand} />
          <ExperteSpur zustand={zustand} />
        </div>
      </div>

      <Verlauf zustand={zustand} />
    </div>
  );
}
