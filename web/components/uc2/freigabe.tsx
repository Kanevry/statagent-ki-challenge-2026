"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Feld, Fliesstext, Knopf, Piktogramm, Status, Ueberschrift } from "@kic/ui/basis";
import { formatZeit, pruefeName } from "@kic/ui/bausteine";
import type { Modus } from "../../app/api/uc2/_lib/proxy";
import { klassen, fokus } from "./klassen";
import { Stand } from "./stand";
import { endstand, type FallZustand } from "./zustand";

// Freigabe des Berichts mit Namen (PRD S8, U2-2; Pen-Szene 4 "ein Kern für alle drei"). Unter "Am Ende gilt" steht
// die Marke "Entwurf", bis ein Mensch mit Vor- und Nachnamen freigegeben hat; danach "Freigegeben von <Name>, <Zeit>".
// Gebaut aus den Bausteinen von @kic/ui und der Namensprüfung `pruefeName` wie die FreigabeKarte (UC3). Die Karte
// selbst passt nicht: sie zeigt den Vorschlag eines Agenten mit Zahlen vorher und nachher.
// Im Vorführmodus (aufgezeichnete Verhandlung) wird nichts gespeichert; das steht sichtbar dabei.

/** `name` und `begruendung` fehlen, wenn der Bericht öffentlich ausgeliefert wird (Personenschutz, `uc2.api.belegfilter`). */
export type Entscheidung =
  | { art: "freigegeben"; name?: string; zeit: string }
  | { art: "abgelehnt"; name?: string; zeit: string; begruendung?: string };

export type FreigabeAuftrag = { name: string; entscheidung: "freigegeben" | "abgelehnt"; begruendung?: string };

/** Speichert eine Entscheidung und liefert die Zeit des Servers. Wirft mit einem Satz für die Seite, wenn es scheitert. */
export type Speichern = (auftrag: FreigabeAuftrag) => Promise<{ zeitpunkt?: string | null } | void>;

export const VORFUEHRUNG_HINWEIS = "Vorführung: nichts gespeichert";
export const SATZ = "Das Ergebnis der Verhandlung wird als geprüft markiert und kommt mit deinem Namen ins Protokoll.";
/** In der Vorführung bleibt nichts stehen; der Satz darf nicht das Gegenteil sagen. */
export const VORFUEHRUNG_SATZ = "In der Vorführung wird nichts gespeichert. Im echten Betrieb kommt dein Name ins Protokoll.";
/** Längste Begründung; die Route und die Python-API lehnen mehr ab. */
export const MAX_BEGRUENDUNG = 500;
/** Textknopf mit Mindesthöhe 44 px für Touch (wie in UC3). */
const TEXTKNOPF = "inline-flex min-h-11 items-center font-sans text-14 font-semibold text-ink underline underline-offset-4";
const NAME_HINWEIS = "Bitte den eigenen Vor- und Nachnamen eintragen, „Team“ gilt nicht.";

/** Aus dem Bericht der API (`freigabe: {name?, zeit, entscheidung, begruendung?} | null`); öffentlich ohne Name und Grund. */
export function entscheidungAusBericht(bericht: unknown): Entscheidung | null {
  const f = (bericht as { freigabe?: unknown } | null)?.freigabe;
  if (!f || typeof f !== "object") return null;
  const { name, zeit, entscheidung, begruendung } = f as Record<string, unknown>;
  if (typeof zeit !== "string") return null;
  const person = typeof name === "string" && name.trim() ? { name } : {};
  if (entscheidung === "freigegeben") return { art: "freigegeben", ...person, zeit };
  if (entscheidung === "abgelehnt") {
    return { art: "abgelehnt", ...person, zeit, ...(typeof begruendung === "string" && begruendung.trim() ? { begruendung } : {}) };
  }
  return null;
}

/** Entwurf-Marke am Ergebnis; Text statt nur Farbe. */
export function EntwurfMarke() {
  return (
    <span
      className="inline-flex items-center rounded-full bg-warn-bg px-3 py-0.5 font-sans text-12 font-semibold text-warn-fg"
      data-testid="uc2-entwurf"
    >
      Entwurf
    </span>
  );
}

/** Marke am Ergebnis nach einer Ablehnung: der Bericht gilt nicht als geprüft. */
export function AbgelehntMarke() {
  return (
    <span
      className="inline-flex items-center rounded-full bg-err-bg px-3 py-0.5 font-sans text-12 font-semibold text-err-fg"
      data-testid="uc2-abgelehnt"
    >
      Abgelehnt
    </span>
  );
}

/** Wer wann entschieden hat; ohne Namen (öffentlich) nur „am <Zeit>“. */
export function entscheidungSatz(e: Entscheidung): string {
  const wort = e.art === "freigegeben" ? "Freigegeben" : "Abgelehnt";
  return e.name ? `${wort} von ${e.name}, ${formatZeit(e.zeit)}` : `${wort} am ${formatZeit(e.zeit)}`;
}

/** Speichern über die Route der Seite; die Antwort trägt feste Sätze, die direkt angezeigt werden. */
export async function speichereAmServer(fallId: string, auftrag: FreigabeAuftrag): Promise<{ zeitpunkt?: string | null }> {
  let antwort: Response;
  try {
    antwort = await fetch(`/api/uc2/faelle/${encodeURIComponent(fallId)}/freigabe`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(auftrag),
      cache: "no-store",
    });
  } catch {
    throw new Error("Keine Verbindung zum Server.");
  }
  const daten: unknown = await antwort.json().catch(() => null);
  if (!antwort.ok) {
    const satz = daten && typeof daten === "object" && "fehler" in daten ? String((daten as { fehler: unknown }).fehler) : "";
    throw new Error(satz || "Der Server hat die Freigabe nicht angenommen.");
  }
  const zeitpunkt = (daten as { zeitpunkt?: unknown } | null)?.zeitpunkt;
  return { zeitpunkt: typeof zeitpunkt === "string" ? zeitpunkt : null };
}

function fehlertext(fehler: unknown): string {
  const meldung = fehler instanceof Error ? fehler.message.trim() : "";
  return meldung ? `Nicht gespeichert. ${meldung}` : "Nicht gespeichert. Bitte noch einmal versuchen.";
}

export interface FreigabeKarteUc2Props {
  fallId: string;
  modus: Modus;
  /** Schon entschieden (aus dem Bericht oder eben in dieser Seite). */
  entscheidung: Entscheidung | null;
  onEntschieden: (e: Entscheidung) => void;
  speichern?: Speichern;
}

/** Karte der Freigabe: ein Satz, Name, "Freigeben" und "Ablehnen". Nach der Entscheidung steht nur das Ergebnis da. */
export function FreigabeBericht({ fallId, modus, entscheidung, onEntschieden, speichern }: FreigabeKarteUc2Props) {
  const basisId = useId();
  const vorfuehrung = modus === "vorfuehrung";
  const [name, setName] = useState("");
  const [ablehnen, setAblehnen] = useState(false);
  const [begruendung, setBegruendung] = useState("");
  const [laeuft, setLaeuft] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [fokusZaehler, setFokusZaehler] = useState(0);
  const ergebnisId = `${basisId}-ergebnis`;
  const begruendungId = `${basisId}-begruendung`;
  const ablehnenId = `${basisId}-ablehnen`;
  const fokusNachWechsel = useRef(false);

  useEffect(() => {
    if (!fokusNachWechsel.current) return;
    fokusNachWechsel.current = false;
    document.getElementById(ablehnen ? begruendungId : ablehnenId)?.focus();
  }, [ablehnen, begruendungId, ablehnenId]);
  useEffect(() => {
    if (fokusZaehler > 0) document.getElementById(ergebnisId)?.focus();
  }, [fokusZaehler, ergebnisId]);

  const pruefung = pruefeName(name);
  const nameFehler = name.trim() && !pruefung.gueltig ? pruefung.grund : undefined;
  const grund = begruendung.trim();

  function wechsle(wert: boolean) {
    fokusNachWechsel.current = true;
    setAblehnen(wert);
  }

  // Enter soll nie freigeben, auch nicht über ein umgebendes Formular.
  function enterSperren(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") e.preventDefault();
  }

  async function ausfuehren(art: "freigegeben" | "abgelehnt") {
    if (!pruefung.gueltig || laeuft || (art === "abgelehnt" && !grund)) return;
    setLaeuft(true);
    setFehler(null);
    try {
      let zeit = new Date().toISOString();
      // Vorführung: keine Anfrage, nichts wird gespeichert. Die Entscheidung wirkt nur in dieser Seite.
      if (!vorfuehrung) {
        const auftrag: FreigabeAuftrag = { name: pruefung.name, entscheidung: art, ...(art === "abgelehnt" ? { begruendung: grund } : {}) };
        const antwort = await (speichern ?? ((a) => speichereAmServer(fallId, a)))(auftrag);
        const vomServer = (antwort as { zeitpunkt?: unknown } | undefined | null)?.zeitpunkt;
        if (typeof vomServer === "string" && vomServer.trim()) zeit = vomServer;
      }
      onEntschieden(art === "freigegeben" ? { art, name: pruefung.name, zeit } : { art, name: pruefung.name, zeit, begruendung: grund });
    } catch (f) {
      setFehler(fehlertext(f));
    } finally {
      setLaeuft(false);
      setFokusZaehler((n) => n + 1);
    }
  }

  const nameFeldId = `${basisId}-name`;
  const titelId = `${basisId}-titel`;

  return (
    <article
      aria-labelledby={titelId}
      className="flex flex-col gap-4 rounded-xl border border-line bg-white p-6"
      data-baustein="freigabe"
      data-zustand={entscheidung?.art ?? "offen"}
      data-testid="uc2-freigabe"
    >
      <Ueberschrift stufe={3} als="h3" id={titelId}>
        Freigabe des Berichts
      </Ueberschrift>
      {!entscheidung && <Fliesstext groesse={14}>{vorfuehrung ? VORFUEHRUNG_SATZ : SATZ}</Fliesstext>}

      {!entscheidung && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-start gap-3 sm:flex-nowrap">
            <Feld
              id={nameFeldId}
              className="min-w-0 flex-1 basis-60"
              label="Vor- und Nachname"
              name="freigabe-name"
              autoComplete="off"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={enterSperren}
              hinweis={NAME_HINWEIS}
              fehler={nameFehler}
            />
            {!ablehnen && (
              <Knopf className="min-h-11 sm:mt-7" disabled={!pruefung.gueltig || laeuft} onClick={() => void ausfuehren("freigegeben")}>
                <Piktogramm name="haken" />
                Freigeben
              </Knopf>
            )}
          </div>
          {ablehnen && (
            <Feld
              id={begruendungId}
              label="Begründung der Ablehnung"
              name="freigabe-begruendung"
              autoComplete="off"
              required
              value={begruendung}
              maxLength={MAX_BEGRUENDUNG}
              onChange={(e) => setBegruendung(e.target.value)}
              onKeyDown={enterSperren}
            />
          )}
          <div className="flex flex-wrap items-center gap-6">
            {ablehnen ? (
              <>
                <Knopf art="sekundaer" className="min-h-11" disabled={!pruefung.gueltig || !grund || laeuft} onClick={() => void ausfuehren("abgelehnt")}>
                  Ablehnung speichern
                </Knopf>
                <button
                  type="button"
                  className={klassen(TEXTKNOPF, fokus)}
                  onClick={() => wechsle(false)}
                  disabled={laeuft}
                >
                  Zurück
                </button>
              </>
            ) : (
              <button
                id={ablehnenId}
                type="button"
                className={klassen(TEXTKNOPF, fokus)}
                onClick={() => wechsle(true)}
                disabled={laeuft}
              >
                Ablehnen
              </button>
            )}
          </div>
        </div>
      )}

      {/* Live-Region von Anfang an da (leer), damit Screenreader die Änderung melden; nach einem Ergebnis geht der
          Fokus hierher. Leer nimmt sie über `empty:-mt-4` keinen Platz ein. */}
      <div
        id={ergebnisId}
        tabIndex={-1}
        aria-live="polite"
        data-meldung="freigabe"
        className={klassen("flex flex-col gap-2 empty:-mt-4", fokus)}
      >
        {entscheidung ? (
          entscheidung.art === "freigegeben" ? (
            <Status art="ok">{entscheidungSatz(entscheidung)}</Status>
          ) : (
            <>
              <Status art="info">{entscheidungSatz(entscheidung)}</Status>
              {entscheidung.begruendung && <Fliesstext groesse={14}>{`Begründung: ${entscheidung.begruendung}`}</Fliesstext>}
            </>
          )
        ) : laeuft ? (
          <Status art="info">Wird gespeichert</Status>
        ) : fehler ? (
          <Status art="fehler" role="alert">
            {fehler}
          </Status>
        ) : null}
      </div>
      {vorfuehrung && (
        <p className="border-l-2 border-line pl-3 font-sans text-12 text-slate" data-testid="uc2-freigabe-vorfuehrung">
          {VORFUEHRUNG_HINWEIS}
        </p>
      )}
    </article>
  );
}

/**
 * "Am Ende gilt" mit Freigabe: Marke "Entwurf" am Ergebnis, bis entschieden ist (nach einer Ablehnung "Abgelehnt"), darunter die Karte. Live liest die
 * Seite eine frühere Entscheidung aus dem Bericht der API; in der Vorführung bleibt alles in der Seite.
 */
export function StandMitFreigabe({
  zustand,
  fallId,
  modus,
  speichern,
}: {
  zustand: FallZustand;
  fallId: string;
  modus: Modus;
  speichern?: Speichern;
}) {
  const [entscheidung, setEntscheidung] = useState<Entscheidung | null>(null);
  const fertig = zustand.status === "fertig" && endstand(zustand) !== null;
  const vorfuehrung = modus === "vorfuehrung";

  useEffect(() => {
    if (!fertig || vorfuehrung) return;
    let abgebrochen = false;
    fetch(`/api/uc2/faelle/${encodeURIComponent(fallId)}`, { cache: "no-store" })
      .then((antwort) => (antwort.ok ? antwort.json() : null))
      .then((bericht: unknown) => {
        const frueher = entscheidungAusBericht(bericht);
        if (!abgebrochen && frueher) setEntscheidung(frueher);
      })
      .catch(() => {
        // Ohne den Bericht gilt der Fall als offen; der Server lehnt eine zweite Entscheidung ohnehin ab.
      });
    return () => {
      abgebrochen = true;
    };
  }, [fertig, vorfuehrung, fallId]);

  const marke = !fertig ? undefined : !entscheidung ? <EntwurfMarke /> : entscheidung.art === "abgelehnt" ? <AbgelehntMarke /> : undefined;

  return (
    <>
      <Stand zustand={zustand} marke={marke} />
      {fertig && (
        <FreigabeBericht fallId={fallId} modus={modus} entscheidung={entscheidung} onEntschieden={setEntscheidung} speichern={speichern} />
      )}
    </>
  );
}
