"use client";

import { useId, useState, type FormEvent } from "react";
import { Fliesstext, Knopf, knopfKlassen, Status, Ueberschrift } from "@kic/ui/basis";
import { formatZeit, pruefeName } from "@kic/ui/bausteine";
import type { WebAntrag } from "./antrag";
import { pruefungSchluessel, useLotse } from "./lotse-kontext";

// Abschluss des vorausgefüllten Antrags: Ein Mensch markiert den Entwurf mit Vor- und Nachnamen als geprüft
// (Namensregel `pruefeName` aus @kic/ui, wie in UC3). Die Prüfung liegt im LotseAnbieter je Antrag und Sitzung und
// gilt deshalb über alle Unterseiten; gespeichert und abgeschickt wird nichts. Das PDF (nur live) gibt es erst danach.

/** Satz in Bürgersprache zur Zahl der eingetragenen Angaben. */
export function entwurfSatz(anzahl: number): string {
  if (anzahl === 0) return "Der Lotse hat noch keine Angabe eingetragen. Sie füllen den Antrag selbst aus.";
  const angaben = anzahl === 1 ? "eine Angabe" : `${anzahl} Angaben`;
  return `Der Lotse hat ${angaben} aus Ihrem Gespräch eingetragen. Bitte prüfen Sie jede Angabe, bevor Sie den Antrag verwenden.`;
}

/** Der eine wahre Satz zur Prüfung: wo der Name steht und dass nichts gespeichert oder abgeschickt wird. */
export const PRUEF_SATZ = "Ihr Name steht nur auf diesem Entwurf und gilt in dieser Sitzung, gespeichert oder abgeschickt wird nichts.";

export type EntwurfPruefungProps = {
  antrag: WebAntrag;
  /** Live gibt es das PDF; im aufgezeichneten Beispiel nicht. */
  live: boolean;
  /** Adresse des PDFs (nur live). */
  pdf: string;
  ebene: "h2" | "h3";
};

export function EntwurfPruefung({ antrag, live, pdf, ebene }: EntwurfPruefungProps) {
  const basisId = useId();
  const { pruefungen, setPruefung } = useLotse();
  const [name, setName] = useState("");
  const geprueft = pruefungen[pruefungSchluessel(antrag)];
  const pruefung = pruefeName(name);
  // Der Grund für den gesperrten Knopf steht schon beim Tippen da.
  const nameFehler = name.trim() && !pruefung.gueltig ? pruefung.grund : undefined;
  const feldId = `${basisId}-name`;
  const satzId = `${basisId}-satz`;
  const fehlerId = `${basisId}-fehler`;
  const pdfHinweisId = `${basisId}-pdf`;
  const titelId = `${basisId}-titel`;

  function markieren(ereignis: FormEvent<HTMLFormElement>) {
    ereignis.preventDefault();
    if (!pruefung.gueltig) return;
    setPruefung(antrag, { name: pruefung.name, zeit: new Date().toISOString() });
    setName("");
  }

  return (
    <section
      aria-labelledby={titelId}
      className="flex max-w-3xl flex-col gap-4 rounded border border-line bg-white p-4 md:p-6"
      data-uc1-pruefung={geprueft ? "geprueft" : "offen"}
    >
      <Ueberschrift stufe={3} als={ebene} id={titelId}>
        Entwurf prüfen
      </Ueberschrift>
      <Fliesstext groesse={14}>{entwurfSatz(antrag.befuellt.length)}</Fliesstext>

      <div aria-live="polite">
        {geprueft ? (
          <Status art="ok" data-testid="uc1-entwurf-stand">
            {`Entwurf geprüft von ${geprueft.name}, ${formatZeit(geprueft.zeit)}`}
          </Status>
        ) : (
          <Status art="warnung" data-testid="uc1-entwurf-stand">
            Entwurf nicht geprüft
          </Status>
        )}
      </div>

      {geprueft ? (
        <div>
          <Knopf art="sekundaer" className="min-h-11" onClick={() => setPruefung(antrag, null)}>
            Prüfung zurücknehmen
          </Knopf>
        </div>
      ) : (
        <form onSubmit={markieren} noValidate className="flex flex-col gap-2">
          <label htmlFor={feldId} className="font-sans text-14 font-semibold text-ink">
            Ihr Vor- und Nachname
          </label>
          <div className="flex flex-col items-start gap-3">
            <input
              id={feldId}
              name="pruef-name"
              type="text"
              autoComplete="name"
              value={name}
              aria-invalid={nameFehler ? true : undefined}
              aria-describedby={[satzId, nameFehler && fehlerId].filter(Boolean).join(" ")}
              onChange={(e) => setName(e.target.value)}
              className={`h-11 w-full min-w-0 rounded border bg-white px-4 font-sans text-16 text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen ${nameFehler ? "border-err-fg" : "border-slate"}`}
            />
            <Knopf type="submit" className="min-h-11" disabled={!pruefung.gueltig}>
              Entwurf als geprüft markieren
            </Knopf>
          </div>
          {nameFehler && (
            <Status id={fehlerId} art="fehler">
              {nameFehler}
            </Status>
          )}
        </form>
      )}
      <Fliesstext id={satzId} groesse={14} ton="gedaempft">
        {PRUEF_SATZ}
      </Fliesstext>

      {live ? (
        <div className="flex flex-col items-start gap-2">
          {geprueft ? (
            <a href={pdf} download={`antrag-${antrag.art}-entwurf.pdf`} className={knopfKlassen("primaer", "min-h-11")}>
              Antrag als PDF speichern
            </a>
          ) : (
            <>
              <Knopf className="min-h-11" disabled aria-describedby={pdfHinweisId}>
                Antrag als PDF speichern
              </Knopf>
              <Fliesstext id={pdfHinweisId} groesse={14} ton="gedaempft">
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
