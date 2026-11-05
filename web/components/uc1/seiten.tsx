"use client";

import Link from "next/link";
import { useState } from "react";
import { Fliesstext, Knopf, knopfKlassen, Leerzustand } from "@kic/ui/basis";
import { Antworten, BeispielStart } from "./antworten";
import { useLotse, type Wechsel } from "./lotse-kontext";
import { Situation, SITUATION_FELD_ID } from "./situation";
import { leistungName } from "./leistungen";
import { Kopf } from "./teile";

const linkKnopf =
  "inline-flex min-h-11 items-center px-1 font-sans text-14 text-gruen underline hover:no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen";

/** Die Situation klein über der Hauptaussage, mit „ändern“ und „Neue Situation“. */
function SituationKurz({ text, aendern, neu }: { text: string; aendern: () => void; neu: () => void }) {
  return (
    <div className="flex max-w-3xl flex-wrap items-center gap-x-2 border-b border-line pb-2" data-testid="uc1-situation-kurz">
      <Fliesstext groesse={14} ton="gedaempft" className="min-w-0 flex-1 basis-64">
        {`Ihre Situation: ${text}`}
      </Fliesstext>
      <button type="button" className={linkKnopf} onClick={aendern}>
        ändern
      </button>
      <button type="button" className={linkKnopf} onClick={neu}>
        Neue Situation
      </button>
    </div>
  );
}

/**
 * Konkrete Überschrift: „Pflegegeld kommt für Sie in Frage“, bei mehreren „A und B kommen für Sie in Frage“. Die
 * Person („für Ihre Mutter“) nennt der Kern nicht sicher, deshalb immer „für Sie“.
 */
export function leistungenTitel(ids: readonly string[]): string {
  const namen = ids.map(leistungName);
  const letzter = namen.at(-1) ?? "";
  if (namen.length <= 1) return `${letzter} kommt für Sie in Frage`;
  return `${namen.slice(0, -1).join(", ")} und ${letzter} kommen für Sie in Frage`;
}

/**
 * /uc1 mit einer Hauptaussage je Screen (Owner-Regel): ohne Antwort oder beim Ändern die Eingabe (KN6mU, ytfvF);
 * bei einer Rückfrage die Rückfrage mit Antwortfeld; bei einer Antwort die Leistungen (B1gvr). Die Situation steht
 * dann nur klein darüber.
 */
export function StartSeite({ beispiel }: { beispiel: boolean }) {
  const { verlauf, setEntwurf, neuBeginnen, spielt } = useLotse();
  // Ändern gilt für genau diesen Verlauf; kommt eine neue Antwort, ist die Eingabe wieder zu.
  const [geaendertBei, setGeaendertBei] = useState<readonly Wechsel[] | null>(null);
  const aendert = geaendertBei === verlauf;
  const letzte = verlauf.at(-1)?.antwort;
  const situation = verlauf[0]?.eingabe ?? "";

  function aendern() {
    if (spielt) return;
    setEntwurf(situation);
    setGeaendertBei(verlauf);
    requestAnimationFrame(() => document.getElementById(SITUATION_FELD_ID)?.focus());
  }

  function neu() {
    neuBeginnen();
    setGeaendertBei(null);
    requestAnimationFrame(() => document.getElementById(SITUATION_FELD_ID)?.focus());
  }

  if (!letzte || aendert) {
    return (
      <>
        <BeispielStart aktiv={beispiel} />
        <Kopf titel="Erzählen Sie, was los ist" unter="Mit eigenen Worten. Rückfragen kommen nur, wenn etwas fehlt." schritt={1} />
        <Situation
          zusatz={
            aendert ? (
              <Knopf art="sekundaer" className="min-h-11" onClick={() => setGeaendertBei(null)}>
                Zurück zur Antwort
              </Knopf>
            ) : undefined
          }
        />
        {!aendert && <Antworten />}
      </>
    );
  }

  const rueckfrage = letzte.verhalten === "rueckfrage";
  const anzahl = letzte.leistungen.length;
  return (
    <>
      <BeispielStart aktiv={beispiel} />
      <SituationKurz text={situation} aendern={aendern} neu={neu} />
      {rueckfrage ? (
        <Kopf titel="Eine Angabe fehlt noch" schritt={1} />
      ) : anzahl > 0 ? (
        <Kopf titel={leistungenTitel(letzte.leistungen)} schritt={2} />
      ) : (
        <Kopf titel="Die Antwort des Lotsen" unter="Jede Angabe hat eine Quelle, wenn es eine gibt." schritt={1} />
      )}
      <Antworten onAendern={aendern} />
    </>
  );
}

/** /uc1/leistungen: dieselben Antworten, solange die Seite offen ist; sonst ein Leerzustand. */
export function LeistungenSeite() {
  const { verlauf, lage } = useLotse();
  const leistungen = verlauf.at(-1)?.antwort.leistungen ?? [];
  return (
    <>
      {leistungen.length > 0 ? (
        <Kopf titel={leistungenTitel(leistungen)} schritt={2} />
      ) : (
        <Kopf titel="Ihre Leistungen" unter="Hier stehen die Leistungen zu Ihrer Situation." schritt={1} />
      )}
      {verlauf.length === 0 && lage.art !== "laden" && lage.art !== "fehler" ? (
        <Leerzustand
          satz="Erst eine Situation erzählen, dann stehen hier die passenden Leistungen."
          aktion={
            <Link href="/uc1" className={knopfKlassen("primaer", "min-h-11")}>
              Situation erzählen
            </Link>
          }
        />
      ) : (
        <Antworten situationFehler />
      )}
    </>
  );
}
