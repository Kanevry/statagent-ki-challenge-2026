"use client";

import { useId, useState } from "react";
import { Fliesstext, Knopf, knopfKlassen, Status } from "@kic/ui/basis";
import { FreigabeKarte, formatZeit } from "@kic/ui/bausteine";
import type { WebAntrag } from "./antrag";
import { antragName } from "./leistungen";

// Abschluss des vorausgefüllten Antrags: Ein Mensch prüft den Entwurf und gibt ihn mit Vor- und Nachnamen frei
// (FreigabeKarte aus @kic/ui, Namensregel wie in UC3). Die Prüfung lebt nur im Zustand dieser Seite; gespeichert
// und abgeschickt wird nichts. Das PDF (nur live) gibt es erst nach der Freigabe.

export type EntwurfStand =
  | { art: "offen" }
  | { art: "geprueft"; name: string; zeit: string }
  | { art: "abgelehnt"; name: string; zeit: string; begruendung: string };

/** „Antrag auf Pflegegeld (PAL080) als Entwurf vorausfüllen“. */
export function entwurfAnweisung(antrag: Pick<WebAntrag, "art" | "code">): string {
  return `Antrag auf ${antragName(antrag.art)}${antrag.code ? ` (${antrag.code})` : ""} als Entwurf vorausfüllen`;
}

/** Satz in Bürgersprache zur Zahl der eingetragenen Angaben. */
export function entwurfSatz(anzahl: number): string {
  if (anzahl === 0) return "Der Lotse hat noch keine Angabe eingetragen. Sie füllen den Antrag selbst aus.";
  const angaben = anzahl === 1 ? "eine Angabe" : `${anzahl} Angaben`;
  return `Der Lotse hat ${angaben} aus Ihrem Gespräch eingetragen. Bitte prüfen Sie jede Angabe, bevor Sie den Antrag verwenden.`;
}

export type EntwurfPruefungProps = {
  antrag: WebAntrag;
  /** Live gibt es das PDF; im aufgezeichneten Beispiel nicht. */
  live: boolean;
  /** Adresse des PDFs (nur live). */
  pdf: string;
  ebene: "h2" | "h3";
};

export function EntwurfPruefung({ antrag, live, pdf, ebene }: EntwurfPruefungProps) {
  const hinweisId = useId();
  const [stand, setStand] = useState<EntwurfStand>({ art: "offen" });
  // Neue Runde nach einer Ablehnung: die Karte beginnt dann wieder leer.
  const [runde, setRunde] = useState(0);
  // Zeitpunkt, zu dem der Entwurf auf dieser Seite vorliegt; steht in der Karte unter der Anweisung.
  const [erstellt] = useState(() => new Date().toISOString());
  const geprueft = stand.art === "geprueft";

  function freigeben(name: string) {
    const zeit = new Date().toISOString();
    setStand({ art: "geprueft", name, zeit });
    return { zeitpunkt: zeit };
  }

  function ablehnen(name: string, begruendung: string) {
    const zeit = new Date().toISOString();
    setStand({ art: "abgelehnt", name, zeit, begruendung });
    return { zeitpunkt: zeit };
  }

  return (
    <section aria-label="Entwurf prüfen" className="flex max-w-3xl flex-col gap-4" data-uc1-pruefung={stand.art}>
      <FreigabeKarte
        key={runde}
        eintrag={{ anweisung: entwurfAnweisung(antrag), name: "Ihre Anfrage", zeit: erstellt }}
        vorher={0}
        nachher={antrag.befuellt.length}
        groesse="Angaben"
        satz={entwurfSatz(antrag.befuellt.length)}
        onFreigeben={freigeben}
        onAblehnen={ablehnen}
        ebene={ebene}
      />

      <div className="flex flex-col items-start gap-2">
        {geprueft ? (
          <Status art="ok" data-testid="uc1-entwurf-stand">
            {`Entwurf geprüft von ${stand.name}, ${formatZeit(stand.zeit)}`}
          </Status>
        ) : (
          <Status art="warnung" data-testid="uc1-entwurf-stand">
            Entwurf nicht geprüft
          </Status>
        )}
        <Fliesstext groesse={14} ton="gedaempft">
          Die Prüfung gilt für diesen Entwurf auf diesem Gerät. Abgeschickt wird nichts.
        </Fliesstext>
        {stand.art === "abgelehnt" && (
          <Knopf
            art="sekundaer"
            className="min-h-11"
            onClick={() => {
              setStand({ art: "offen" });
              setRunde((n) => n + 1);
            }}
          >
            Noch einmal prüfen
          </Knopf>
        )}
      </div>

      {live ? (
        <div className="flex flex-col items-start gap-2">
          {geprueft ? (
            <a href={pdf} download={`antrag-${antrag.art}-entwurf.pdf`} className={knopfKlassen("primaer", "min-h-11")}>
              Antrag als PDF speichern
            </a>
          ) : (
            <>
              <Knopf className="min-h-11" disabled aria-describedby={hinweisId}>
                Antrag als PDF speichern
              </Knopf>
              <Fliesstext id={hinweisId} groesse={14} ton="gedaempft">
                Erst prüfen, dann speichern.
              </Fliesstext>
            </>
          )}
        </div>
      ) : (
        <Fliesstext groesse={14} ton="gedaempft">
          Das PDF entsteht nur im echten Gespräch. Hier sehen Sie ein aufgezeichnetes Beispiel.
        </Fliesstext>
      )}
    </section>
  );
}
