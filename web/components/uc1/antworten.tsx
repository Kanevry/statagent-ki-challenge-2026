"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, type FormEvent } from "react";
import { Akzent, Fliesstext, Knopf, knopfKlassen, Status, Ueberschrift } from "@kic/ui/basis";
import { ersterSatz, traegerName, type Aussage, type WebAntwort } from "./antwort";
import { antragLeistung, leistungName } from "./leistungen";
import { useLotse, type Lage, type Wechsel } from "./lotse-kontext";
import { GESPERRT } from "./situation";
import { StelleKasten, stellenGruppen } from "./stelle";
import { Beleg, Fundstelle, KiKennzeichnung, KOPF_ID, MitTelefon, OHNE_STELLE } from "./teile";

// Antworten des Lotsen (#35, Urteil der Sichtprüfung): Rückfrage mit Antwortknöpfen, Leistungen mit Begründung und
// „Antrag vorbereiten“, daneben die zuständige Stelle, Quellen hinter „Details“. Eine Einschätzung wie „sehr
// wahrscheinlich“ rechnet der Kern nicht, deshalb steht sie hier nicht.

/** Feld der aktiven Rückfrage; nach einer neuen Rückfrage ohne Knöpfe springt der Fokus dorthin. */
export const RUECKFRAGE_FELD_ID = "uc1-rueckfrage";

const FELD =
  "h-11 rounded border border-slate bg-white px-4 font-sans text-16 text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen";

function Rueckfrage({ antwort, aktiv }: { antwort: WebAntwort; aktiv: boolean }) {
  const { antworten, antwortEntwurf, setAntwortEntwurf, lage, spielt } = useLotse();
  const frage = antwort.rueckfrage ?? antwort.text;
  const optionen = antwort.rueckfrage_optionen;
  const mitKnoepfen = aktiv && optionen.length > 0;
  const laedt = lage.art === "laden";
  // Während eine Aufnahme läuft, geht keine Antwort live hinaus (sonst mit der aufgezeichneten Sitzung).
  const gesperrt = laedt || spielt;
  const feldId = RUECKFRAGE_FELD_ID;
  const fehler = aktiv && lage.art === "fehler" && !lage.replay && lage.ort === "rueckfrage" ? lage.meldung : null;

  function absenden(ereignis: FormEvent<HTMLFormElement>) {
    ereignis.preventDefault();
    if (!gesperrt) void antworten(antwortEntwurf);
  }

  if (!aktiv) return <Fliesstext className="font-semibold"><MitTelefon text={frage} /></Fliesstext>;

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      {mitKnoepfen ? (
        // Mit Knöpfen reicht der erste Satz; die Erklärung zeigen die Knöpfe selbst.
        <fieldset className="flex flex-col gap-4" data-uc1-optionen="">
          <legend className="mb-4 font-sans text-20 font-semibold text-ink">{ersterSatz(frage)}</legend>
          <div className="flex flex-wrap gap-2">
            {optionen.map((option) => (
              <Knopf
                key={option.text}
                art="sekundaer"
                aria-disabled={gesperrt}
                className={GESPERRT}
                onClick={() => {
                  if (!gesperrt) void antworten(option.antwort);
                }}
              >
                {option.text}
              </Knopf>
            ))}
          </div>
        </fieldset>
      ) : (
        <Fliesstext className="font-semibold md:text-20"><MitTelefon text={frage} /></Fliesstext>
      )}
      <form onSubmit={absenden} noValidate className="flex flex-col gap-2">
        <label htmlFor={feldId} className="font-sans text-14 font-semibold text-ink">
          {mitKnoepfen ? "Oder selbst schreiben" : "Ihre Antwort"}
        </label>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <input
            id={feldId}
            value={antwortEntwurf}
            maxLength={1000}
            readOnly={spielt}
            aria-invalid={fehler ? true : undefined}
            onChange={(e) => setAntwortEntwurf(e.target.value)}
            className={`${FELD} sm:flex-1`}
          />
          <Knopf type="submit" art={mitKnoepfen ? "sekundaer" : "primaer"} aria-disabled={gesperrt} className={GESPERRT}>
            Antworten
          </Knopf>
        </div>
        {fehler && <Status art="fehler">{fehler}</Status>}
      </form>
    </div>
  );
}

/** Startet nur den Antrag dieser Leistung; die anderen Anträge der Antwort bleiben, wie sie sind. */
function AntragKnopf({ art }: { art: string }) {
  const { antragVorbereiten, spielt } = useLotse();
  const router = useRouter();
  return (
    <div>
      <Knopf
        aria-disabled={spielt}
        className={GESPERRT}
        onClick={() => {
          if (spielt) return;
          void antragVorbereiten([art]);
          router.push("/uc1/antrag");
        }}
      >
        Antrag vorbereiten
      </Knopf>
    </div>
  );
}

/** Erste Aussage, die die Leistung beim Namen nennt („Pflegegeld gibt es, wenn der Pflegebedarf … mehr als 65 Stunden …“), sonst keine. */
export function begruendungFuer(id: string, aussagen: readonly Aussage[]): Aussage | undefined {
  const namen = [leistungName(id), id].map((n) => n.toLowerCase());
  return aussagen.find((a) => namen.some((n) => a.text.toLowerCase().includes(n)));
}

/** Eine Leistung: Begründung mit Beleg (sonst die Stelle mit Fundstelle) und die Hauptaktion. */
function LeistungKarte({ id, antwort, letzte }: { id: string; antwort: WebAntwort; letzte: boolean }) {
  const { aufgezeichnet } = useLotse();
  const begruendung = begruendungFuer(id, antwort.aussagen);
  const stellen = antwort.traeger.filter((t) => !t.leistung || t.leistung === id);
  const art = antwort.antraege.find((a) => antragLeistung(a) === id);
  // Im Beispiel gibt es nur die aufgezeichneten Anträge; für die anderen steht ein ehrlicher Satz.
  const ohneAufnahme = art !== undefined && aufgezeichnet !== null && !aufgezeichnet.includes(art);
  return (
    <li data-uc1-leistung={id} className="flex flex-col items-start gap-3 rounded border border-line bg-white p-4 md:p-6">
      <Ueberschrift stufe={3} als="h2">
        {leistungName(id)}
      </Ueberschrift>
      {begruendung ? (
        <div className="flex flex-col items-start gap-1" data-uc1-begruendung="">
          <Fliesstext><MitTelefon text={begruendung.text} /></Fliesstext>
          <Beleg aussage={begruendung} />
        </div>
      ) : stellen.length === 0 ? (
        <Fliesstext groesse={14} ton="gedaempft" data-uc1-ohne-stelle="">
          {OHNE_STELLE}
        </Fliesstext>
      ) : (
        stellen.map((stelle, i) => (
          <div key={`${i}-${traegerName(stelle)}`} className="flex flex-col items-start gap-1">
            <Fliesstext groesse={14}>{`Zuständig: ${traegerName(stelle)}.`}</Fliesstext>
            <Fundstelle fundstelle={stelle.fundstelle} zitat={stelle.zitat} />
          </div>
        ))
      )}
      {art &&
        // Im aufgezeichneten Gespräch ohne aufgezeichneten Antrag: Leistung, Quelle und Stelle, kein Antragsweg
        // (Jury 05.11.: „im Beispiel nicht aufgezeichnet“ war eine Sackgasse).
        (letzte && ohneAufnahme ? null : letzte ? (
          <AntragKnopf art={art} />
        ) : (
          <Fliesstext groesse={14} ton="gedaempft">
            Dafür gibt es einen Antrag.
          </Fliesstext>
        ))}
    </li>
  );
}

const ZUSAMMENFASSUNG =
  "inline-flex min-h-11 cursor-pointer items-center font-sans text-14 font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen";

/** Leistungen mit Begründung, daneben (Desktop) die zuständige Stelle, die Quellen aufklappbar darunter. */
function Ergebnis({ antwort, letzte }: { antwort: WebAntwort; letzte: boolean }) {
  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        {antwort.leistungen.length > 0 ? (
          <ul className="flex min-w-0 flex-col gap-4" aria-label="Erkannte Leistungen">
            {antwort.leistungen.map((id) => (
              <LeistungKarte key={id} id={id} antwort={antwort} letzte={letzte} />
            ))}
          </ul>
        ) : (
          <Fliesstext className="whitespace-pre-line"><MitTelefon text={antwort.text} /></Fliesstext>
        )}
        {letzte && <StelleKasten gruppen={stellenGruppen(antwort.traeger, [])} className="self-start" />}
      </div>

      {antwort.aussagen.length > 0 && (
        <details className="max-w-3xl border-t border-line pt-2" data-uc1-quellen="">
          <summary className={ZUSAMMENFASSUNG}>Details: Quellen</summary>
          <ul className="flex flex-col gap-4 pt-2" aria-label="Was in den Quellen steht">
            {antwort.aussagen.map((aussage, i) => (
              <li key={`${aussage.quelle}-${i}`} className="flex flex-col items-start gap-2 border-b border-line pb-4">
                <Fliesstext><MitTelefon text={aussage.text} /></Fliesstext>
                {aussage.hinweis_hoehe && (
                  <Fliesstext groesse={14} ton="gedaempft">
                    Die genaue Höhe legt die zuständige Stelle fest.
                  </Fliesstext>
                )}
                <Beleg aussage={aussage} />
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function AntwortBlock({ wechsel, letzte, onAendern }: { wechsel: Wechsel; letzte: boolean; onAendern?: () => void }) {
  const { antwort, eingabe } = wechsel;
  // Bei einer Antwort mit Leistungen trägt die gegliederte Form den Inhalt; der Fließtext stünde doppelt.
  const zeigeText = antwort.verhalten === "abstinenz" || antwort.verhalten === "uebergabe";
  return (
    <article className="flex flex-col gap-4" data-uc1-antwort={antwort.verhalten}>
      {/* Die Eingabe steht nur im eingeklappten Verlauf; oben steht die Situation schon kurz über der Antwort. */}
      {!letzte && <Fliesstext groesse={14} ton="gedaempft">{`Sie: ${eingabe}`}</Fliesstext>}
      {zeigeText && <Fliesstext className="max-w-3xl whitespace-pre-line"><MitTelefon text={antwort.text} /></Fliesstext>}
      {antwort.verhalten === "rueckfrage" && <Rueckfrage antwort={antwort} aktiv={letzte} />}
      {antwort.verhalten === "uebergabe" && antwort.uebergabe_an && (
        <Akzent art="warnung">
          <Fliesstext className="font-semibold">Bitte wenden Sie sich an: <MitTelefon text={antwort.uebergabe_an} /></Fliesstext>
        </Akzent>
      )}
      {antwort.verhalten === "abstinenz" && letzte && (
        <div>
          {onAendern ? (
            <Knopf art="sekundaer" onClick={onAendern} className="min-h-11">
              Frage anders stellen
            </Knopf>
          ) : (
            <Link href="/uc1" className={knopfKlassen("sekundaer", "min-h-11")}>
              Frage anders stellen
            </Link>
          )}
        </div>
      )}
      {antwort.verhalten === "antwort" && <Ergebnis antwort={antwort} letzte={letzte} />}
      {antwort.hinweise.length > 0 && (
        <ul className="flex max-w-3xl flex-col gap-1">
          {antwort.hinweise.map((hinweis, i) => (
            <li key={`${i}-${hinweis}`}>
              <Status art="info"><MitTelefon text={hinweis} /></Status>
            </li>
          ))}
        </ul>
      )}
      <KiKennzeichnung antwort={antwort} />
    </article>
  );
}

function ansage(lage: Lage, verlauf: readonly Wechsel[]): string {
  if (lage.art === "laden") return "Der Lotse liest Ihre Angaben.";
  if (lage.art === "fehler") return lage.meldung;
  const letzte = verlauf.at(-1)?.antwort;
  if (!letzte) return "";
  if (letzte.verhalten === "rueckfrage") return "Der Lotse hat eine Rückfrage.";
  return "Die Antwort ist da.";
}

/**
 * Setzt nach einer neuen Antwort den Fokus auf die neue Hauptaussage: bei einer Rückfrage ohne Knöpfe auf das Antwortfeld,
 * sonst auf die Überschrift der Seite. Beim ersten Anzeigen (Seitenwechsel) bleibt der Fokus, wo er ist.
 */
function useFokusNachAntwort(verlauf: readonly Wechsel[], lage: Lage): void {
  const bekannt = useRef(verlauf.length);
  useEffect(() => {
    if (lage.art !== "bereit" || verlauf.length === bekannt.current) {
      bekannt.current = verlauf.length;
      return;
    }
    bekannt.current = verlauf.length;
    const neue = verlauf.at(-1)?.antwort;
    // Rückfrage ohne Knöpfe: ins Antwortfeld. Mit Knöpfen auf die Überschrift, dann liest man zuerst die Frage.
    const rueckfrage = neue?.verhalten === "rueckfrage" && neue.rueckfrage_optionen.length === 0;
    // Ein Frame Pause: die Seite tauscht erst die Ansicht (Eingabe, Rückfrage, Ergebnis), dann gibt es das Ziel.
    const rahmen = requestAnimationFrame(() => {
      const ziel = (rueckfrage && document.getElementById(RUECKFRAGE_FELD_ID)) || document.getElementById(KOPF_ID);
      ziel?.focus();
    });
    return () => cancelAnimationFrame(rahmen);
  }, [verlauf, lage]);
}

export interface AntwortenProps {
  /** Ändern der Situation auf derselben Seite; fehlt es, führt „Frage anders stellen“ nach /uc1. */
  onAendern?: () => void;
  /** Fehler zur Situation hier zeigen, weil auf der Seite kein Situationsfeld steht. */
  situationFehler?: boolean;
}

/**
 * Verlauf mit Live-Region, KI-Kennzeichnung je Antwort und Fehler mit „Beispiel ansehen“. Hauptaussage ist die letzte
 * Antwort; frühere Schritte stehen eingeklappt unter „Bisheriges Gespräch“.
 */
export function Antworten({ onAendern, situationFehler = false }: AntwortenProps = {}) {
  const { verlauf, lage, beispielAbspielen } = useLotse();
  useFokusNachAntwort(verlauf, lage);
  const frueher = verlauf.slice(0, -1);
  const letzte = verlauf.at(-1);
  return (
    <section aria-label="Antworten des Lotsen" aria-busy={lage.art === "laden"} className="flex w-full max-w-6xl flex-col gap-6">
      <p role="status" aria-live="polite" className="sr-only">
        {ansage(lage, verlauf)}
      </p>
      {lage.art === "fehler" && lage.replay && (
        <div className="flex flex-col items-start gap-4" data-testid="uc1-fehler">
          {/* Ruhig statt rot: der Lotse ist hier nicht erreichbar, das aufgezeichnete Gespräch schon (UI-Regie 05.11.). */}
          <Fliesstext>Der Lotse antwortet gerade nicht. Sehen Sie sich ein aufgezeichnetes Gespräch an.</Fliesstext>
          <Knopf className="min-h-11" onClick={() => void beispielAbspielen()}>
            Aufgezeichnetes Gespräch ansehen
          </Knopf>
        </div>
      )}
      {situationFehler && lage.art === "fehler" && !lage.replay && lage.ort === "situation" && (
        <div className="flex flex-col items-start gap-4" data-testid="uc1-fehler">
          <Status art="fehler">{lage.meldung}</Status>
          <Link href="/uc1" className={knopfKlassen("sekundaer", "min-h-11")}>
            Situation neu erzählen
          </Link>
        </div>
      )}
      {letzte && <AntwortBlock wechsel={letzte} letzte onAendern={onAendern} />}
      {verlauf.some((w) => w.antwort.verhalten === "antwort") && (
        <Fliesstext groesse={14} ton="gedaempft">
          Nicht beurteilt: Krankheiten, Behandlungen und Medikamente. Dafür sind Ärztin oder Arzt da.
        </Fliesstext>
      )}
      {frueher.length > 0 && (
        <details className="border-t border-line pt-4">
          <summary className="inline-flex min-h-11 cursor-pointer items-center font-sans text-14 font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen">
            Bisheriges Gespräch
          </summary>
          <div className="flex flex-col gap-6 pt-4">
            {frueher.map((wechsel, i) => (
              <AntwortBlock key={`${wechsel.antwort.sitzung_id}-${i}`} wechsel={wechsel} letzte={false} />
            ))}
          </div>
        </details>
      )}
    </section>
  );
}

/** Startet das Beispiel einmal, wenn die Seite mit ?beispiel=pflege geöffnet wird. */
export function BeispielStart({ aktiv }: { aktiv: boolean }) {
  const { beispielAbspielen } = useLotse();
  const gestartet = useRef(false);
  useEffect(() => {
    if (!aktiv || gestartet.current) return;
    gestartet.current = true;
    void beispielAbspielen();
  }, [aktiv, beispielAbspielen]);
  return null;
}
