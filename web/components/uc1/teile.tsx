"use client";

import { Fliesstext, Ueberschrift } from "@kic/ui/basis";
import { BelegChip } from "./beleg-chip";
import { formatStand, quelleAnzeige, telefonTeile, type Aussage, type WebAntwort } from "./antwort";
import { modellText, useLotse } from "./lotse-kontext";

// Kleine Teile der UC1-Seiten, nur aus Token-Klassen und Bausteinen von @kic/ui.

const fokus = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen";

/** Die drei Schritte; die zuständige Stelle steht im Antrag (rechte Spalte), keine eigene Seite. */
export const SCHRITTE = ["Situation", "Leistungen", "Antrag"] as const;
export type Schritt = 1 | 2 | 3;

/** Schrittzeiger 1 Situation, 2 Leistungen, 3 Antrag; der aktuelle Schritt trägt aria-current. */
export function Schrittzeiger({ aktiv }: { aktiv: Schritt }) {
  return (
    <ol aria-label="Ihre Schritte" className="flex flex-wrap gap-x-4 gap-y-1 font-sans text-14">
      {SCHRITTE.map((name, i) => {
        const nummer = i + 1;
        const jetzt = nummer === aktiv;
        return (
          <li
            key={name}
            aria-current={jetzt ? "step" : undefined}
            className={jetzt ? "border-b-2 border-gruen font-semibold text-ink" : "border-b-2 border-transparent text-slate"}
          >
            {`${nummer} ${name}`}
          </li>
        );
      })}
    </ol>
  );
}

/** id der h1 jeder UC1-Seite; nach einer neuen Antwort springt der Fokus dorthin (tabIndex -1). */
export const KOPF_ID = "uc1-kopf";

/** Kopfzeile einer UC1-Seite: Titel, wenn nötig eine Unterzeile, darunter der Schrittzeiger. */
export function Kopf({ titel, unter, schritt }: { titel: string; unter?: string; schritt: Schritt }) {
  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Ueberschrift stufe={2} als="h1" id={KOPF_ID} tabIndex={-1} className="focus-visible:outline-none">
          {titel}
        </Ueberschrift>
        {unter && <Fliesstext ton="gedaempft">{unter}</Fliesstext>}
      </div>
      <Schrittzeiger aktiv={schritt} />
    </div>
  );
}

/**
 * Text der KI-Kennzeichnung (AI Act Art. 50), eine Zeile: live mit dem Modell, im Replay mit Datum und Modell der
 * Aufnahme und dem Hinweis auf erfundene Personenangaben.
 */
export function kennzeichnungText(modell: string | null, aufnahme: string | null): string {
  const kopf = modell ? "KI-Antwort, geprüft gegen die Quellen." : "Antwort vom Programm, ohne Sprachmodell.";
  if (aufnahme) {
    const mit = modell ? ` mit ${modell}` : "";
    return `${kopf} Aufgezeichnet am ${aufnahme}${mit}. Personenangaben erfunden.`;
  }
  return modell ? `${kopf} Modell ${modell}.` : kopf;
}

/** Ruhige graue Zeile; ersetzt Aufnahme-Banner und Modell-Pille. */
function Kennzeichnung({ text }: { text: string }) {
  return (
    <Fliesstext groesse={14} ton="gedaempft" data-testid="uc1-ki">
      {text}
    </Fliesstext>
  );
}

/**
 * KI-Kennzeichnung direkt unter jeder Antwort mit dem Modell, das geantwortet hat. Im Replay steht im Kopf der App
 * „Modell nicht erreichbar“; deshalb nennt die Zeile dann das Modell der Aufnahme.
 */
export function KiKennzeichnung({ antwort }: { antwort: Pick<WebAntwort, "modell" | "provider"> }) {
  const { aufnahme } = useLotse();
  return <Kennzeichnung text={kennzeichnungText(modellText(antwort), aufnahme)} />;
}

/** Kennzeichnung einer Seite, deren Inhalt aus Modell oder Aufnahme stammt (Antrag): Modell der letzten Antwort. */
export function SeitenKennzeichnung() {
  const { verlauf, aufnahme, aufnahmeModell } = useLotse();
  const letzte = verlauf.at(-1)?.antwort;
  if (!letzte) return null;
  const modell = aufnahme !== null ? aufnahmeModell : modellText(letzte);
  return <Kennzeichnung text={kennzeichnungText(modell, aufnahme)} />;
}

/** Beleg einer Aussage des Lotsen: Zitat, Quelle und, wenn bekannt, der Stand der Fassung. */
export function Beleg({ aussage }: { aussage: Aussage }) {
  return <BelegChip
      quelle={quelleAnzeige(aussage.quelle)}
      zitat={aussage.zitat}
      fassung={aussage.stand ? formatStand(aussage.stand) : null}
    />;
}

/** Gleiche Einträge nur einmal, die Reihenfolge bleibt (erstes Vorkommen zählt). */
export function einmal(liste: readonly string[]): string[] {
  return [...new Set(liste)];
}

/** Satz, wenn der Kern keine belegte Stelle nennt (er nennt eine Stelle nur mit Beleg). */
export const OHNE_STELLE = "Die zuständige Stelle steht in diesen Quellen nicht fest.";

/**
 * Fundstelle einer Zuständigkeit. Den Beleg-Chip gibt es nur, wenn das Zitat genau zu dieser Fundstelle gehört;
 * sonst steht die Fundstelle als Text, damit sie nicht belegt wirkt.
 */
export function Fundstelle({ fundstelle, zitat }: { fundstelle: string | null; zitat: string | null }) {
  if (!fundstelle) return null;
  if (zitat) return <BelegChip quelle={fundstelle} zitat={zitat} />;
  return (
    <Fliesstext groesse={14} ton="gedaempft" data-uc1-fundstelle-ohne-zitat="">
      {`Fundstelle: ${fundstelle}`}
    </Fliesstext>
  );
}

/** Text mit Notrufnummern (1450, 144) als antippbare tel:-Links; jede Nummer steht genau einmal. */
export function MitTelefon({ text }: { text: string }) {
  return (
    <>
      {telefonTeile(text).map((teil, i) =>
        teil.tel ? (
          <a
            key={i}
            href={`tel:${teil.tel}`}
            className={`inline-flex min-h-11 items-center font-semibold text-gruen underline hover:no-underline ${fokus}`}
          >
            {teil.text}
          </a>
        ) : (
          <span key={i}>{teil.text}</span>
        ),
      )}
    </>
  );
}
