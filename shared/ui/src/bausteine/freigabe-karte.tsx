"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Feld, Fliesstext, Knopf, Piktogramm, Status, Ueberschrift } from "../basis";
import { fokus, klassen } from "../basis/klassen";
import { HerkunftChip, type HerkunftChipProps } from "./herkunft-chip";
import { formatDifferenz, formatProzent, formatZahl, formatZeit, veraenderung } from "./format";
import { ModellPille } from "./modell-pille";
import { pruefeName } from "./name";

/** Ausschnitt eines Protokolleintrags (Schema `shared/schema/protokoll-eintrag.json`). */
export type FreigabeEintrag = {
  /** Die Anweisung, wörtlich. */
  anweisung: string;
  /** Wer sie gegeben hat. */
  name: string;
  /** ISO-Zeitpunkt der Anweisung. */
  zeit: string;
  wirkung?: string | null;
  modell?: string | null;
  ref?: string | null;
};

export type FreigabeEntscheidung =
  | { art: "freigegeben"; name: string; zeit: string }
  | { art: "abgelehnt"; name: string; zeit: string; begruendung: string };

/**
 * Antwort des Servers auf eine Entscheidung. `zeitpunkt` ist der ISO-String aus `meta.freigabe.zeitpunkt`;
 * die Karte zeigt dann diese Zeit statt der Uhr des Browsers.
 */
export type FreigabeAntwort = { zeitpunkt?: string | null } | void;

export type FreigabeKarteProps = {
  eintrag: FreigabeEintrag;
  vorher: number;
  nachher: number;
  /** Ein Satz, was sich ändert. Ohne Angabe entsteht er aus vorher, nachher und `groesse`. */
  satz?: string;
  /** Was gezählt wird, z. B. „Beschäftigte“. */
  groesse?: string;
  /** Diff der Regel, Zeilen mit `+` und `-`; steht in den Details. */
  diff?: string;
  /**
   * Erhält den geprüften, getrimmten Namen. Ein abgelehntes Promise zeigt den Fehler an.
   * Gibt der Server `{ zeitpunkt }` zurück, steht diese Zeit im Ergebnis.
   */
  onFreigeben: (name: string) => FreigabeAntwort | Promise<FreigabeAntwort>;
  /** Erhält Namen und getrimmte Begründung; Rückgabe wie bei `onFreigeben`. */
  onAblehnen: (name: string, begruendung: string) => FreigabeAntwort | Promise<FreigabeAntwort>;
  /** Beleg der Zahl „Nachher“: Abfrage und Lieferung, erscheint als Herkunft-Chip unter der Waage. */
  beleg?: Omit<HerkunftChipProps, "className">;
  /** Schon entschieden, z. B. aus dem Protokoll: die Karte zeigt dann das Ergebnis statt der Eingabe. */
  entscheidung?: FreigabeEntscheidung;
  /** Ebene der Überschrift „Vorschlag des Agenten“ im Seitenaufbau. */
  ebene?: "h2" | "h3" | "h4";
  className?: string;
};

const TITEL = "Vorschlag des Agenten";
const NAME_HINWEIS = "Bitte den eigenen Vor- und Nachnamen eintragen, „Team“ gilt nicht. Der Name kommt ins Protokoll und wird mit der Änderung gespeichert.";

function fehlertext(fehler: unknown): string {
  const meldung = fehler instanceof Error ? fehler.message.trim() : "";
  if (!meldung) return "Nicht gespeichert. Bitte noch einmal versuchen.";
  // Sagt die Route es schon selbst, nicht doppelt (Antrag #135).
  return /^nicht gespeichert\b/i.test(meldung) ? meldung : `Nicht gespeichert. ${meldung}`;
}

function serverZeit(antwort: FreigabeAntwort): string {
  // `void` lässt sich nicht verengen; die Antwort kommt außerdem zur Laufzeit vom Server.
  const zeitpunkt = (antwort as { zeitpunkt?: unknown } | undefined | null)?.zeitpunkt;
  return typeof zeitpunkt === "string" && zeitpunkt.trim() ? zeitpunkt : new Date().toISOString();
}

function Waagschale({
  titel,
  wert,
  art = "feld",
  ton = "ink",
}: {
  titel: string;
  wert: string;
  art?: "feld" | "zeile";
  ton?: "ink" | "gruen";
}) {
  const feld = art === "feld";
  return (
    <div className={klassen("flex flex-col gap-0.5", feld && "rounded-lg border border-line p-3")}>
      <dt className="font-sans text-12 text-slate">{titel}</dt>
      <dd
        className={klassen(
          "tabular-nums",
          feld ? "font-display text-28 font-bold" : "font-mono text-14",
          ton === "gruen" ? "text-gruen" : "text-ink",
        )}
      >
        {wert}
      </dd>
    </div>
  );
}

function Diff({ text }: { text: string }) {
  return (
    // tabIndex 0: lange Zeilen scrollen waagrecht; so erreicht man den Bereich auch per Tastatur (axe
    // scrollable-region-focusable, Antrag #135).
    <pre
      tabIndex={0}
      aria-label="Änderung, Zeilen mit Plus kommen dazu, Zeilen mit Minus fallen weg"
      className={klassen(
        "flex max-w-full flex-col gap-1 overflow-x-auto rounded-lg bg-paper p-3 font-mono text-12 text-ink",
        fokus,
      )}
    >
      {text.split("\n").map((zeile, index) => (
        <span
          key={index}
          className={klassen("block", zeile.startsWith("+") && "text-gruen", zeile.startsWith("-") && "text-err-fg")}
        >
          {zeile || " "}
        </span>
      ))}
    </pre>
  );
}

/**
 * Freigabe einer Änderung (Pen-Frame FgY98) in fester Reihenfolge: Vorschlag mit Modell, wörtliche Anweisung,
 * Diff, Vorher und Nachher, Beleg, Name und „Freigeben“. Ein Ergebnis steht in der Live-Region darunter.
 * Der Knopf wird erst bei gültigem Vor- und Nachnamen aktiv; warum er gesperrt ist, steht schon beim Tippen
 * unter dem Feld. Enter im Namensfeld löst nichts aus.
 */
export function FreigabeKarte({
  eintrag,
  vorher,
  nachher,
  satz,
  groesse,
  diff,
  onFreigeben,
  onAblehnen,
  beleg,
  entscheidung,
  ebene = "h3",
  className,
}: FreigabeKarteProps) {
  const basisId = useId();
  const [name, setName] = useState("");
  const [ablehnen, setAblehnen] = useState(false);
  const [begruendung, setBegruendung] = useState("");
  const [laeuft, setLaeuft] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [ergebnis, setErgebnis] = useState<FreigabeEntscheidung | null>(null);
  // Zählt Ergebnisse (gespeichert oder Fehler); jede Erhöhung legt den Fokus auf die Live-Region mit dem Ergebnis.
  const [fokusZaehler, setFokusZaehler] = useState(0);
  const freigabeId = `${basisId}-freigabe`;
  const begruendungId = `${basisId}-begruendung`;
  const ablehnenId = `${basisId}-ablehnen`;
  // Nach „Ablehnen“ und „Zurück“ verschwindet der geklickte Knopf; der Fokus geht dann gezielt weiter
  // (Begründungsfeld bzw. wieder „Ablehnen“) statt auf body zu fallen.
  const fokusNachWechsel = useRef(false);

  useEffect(() => {
    if (!fokusNachWechsel.current) return;
    fokusNachWechsel.current = false;
    document.getElementById(ablehnen ? begruendungId : ablehnenId)?.focus();
  }, [ablehnen, begruendungId, ablehnenId]);

  function wechsleAblehnen(wert: boolean) {
    fokusNachWechsel.current = true;
    setAblehnen(wert);
  }

  useEffect(() => {
    if (fokusZaehler > 0) document.getElementById(freigabeId)?.focus();
  }, [fokusZaehler, freigabeId]);

  const pruefung = pruefeName(name);
  const entschieden = entscheidung ?? ergebnis;
  const { differenz, prozent } = veraenderung(vorher, nachher);
  const einheit = groesse ? ` ${groesse}` : "";
  const aenderungsSatz =
    satz ??
    (differenz === 0
      ? `Die Zahl bleibt bei ${formatZahl(vorher)}${einheit}.`
      : `Ab jetzt zählen wir ${formatZahl(nachher)}${einheit} statt ${formatZahl(vorher)}.`);

  // Enter soll nie freigeben, auch nicht über ein umgebendes Formular (implizites Absenden).
  function enterSperren(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") e.preventDefault();
  }

  async function ausfuehren(art: FreigabeEntscheidung["art"]) {
    if (!pruefung.gueltig || laeuft) return;
    const grund = begruendung.trim();
    if (art === "abgelehnt" && !grund) return;
    setLaeuft(true);
    setFehler(null);
    try {
      if (art === "freigegeben") {
        const antwort = await onFreigeben(pruefung.name);
        setErgebnis({ art, name: pruefung.name, zeit: serverZeit(antwort) });
      } else {
        const antwort = await onAblehnen(pruefung.name, grund);
        setErgebnis({ art, name: pruefung.name, zeit: serverZeit(antwort), begruendung: grund });
      }
    } catch (e) {
      setFehler(fehlertext(e));
    } finally {
      setLaeuft(false);
      setFokusZaehler((n) => n + 1);
    }
  }

  const titelId = `${basisId}-titel`;
  const hatDetails = Boolean(eintrag.ref || eintrag.wirkung || !diff);
  // Der Grund für den gesperrten Knopf steht sofort beim Tippen da, nicht erst beim Verlassen des Felds.
  const nameFehler = name.trim() && !pruefung.gueltig ? pruefung.grund : undefined;
  const nameFeldId = `${basisId}-name`;
  const nameFehlerId = `${basisId}-name-fehler`;
  const nameHinweisId = `${basisId}-name-hinweis`;

  return (
    <article
      aria-labelledby={titelId}
      className={klassen("flex flex-col gap-4 rounded-xl border border-line bg-white p-6", className)}
      data-baustein="freigabe"
      data-zustand={entschieden?.art ?? "offen"}
    >
      <div className="flex flex-wrap items-center gap-3">
        <Ueberschrift stufe={3} als={ebene} id={titelId}>
          {TITEL}
        </Ueberschrift>
        {eintrag.modell && (
          <ModellPille>
            <span>Modell:</span>
            <span className="font-mono">{eintrag.modell}</span>
            <span>· austauschbar</span>
          </ModellPille>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <blockquote>
          <p className="font-sans text-16 italic text-pretty text-slate">{`„${eintrag.anweisung}“`}</p>
        </blockquote>
        <Fliesstext groesse={12} ton="gedaempft">
          {eintrag.name}
          {" · "}
          <time dateTime={eintrag.zeit}>{formatZeit(eintrag.zeit)}</time>
        </Fliesstext>
      </div>

      {diff && <Diff text={diff} />}

      <Fliesstext groesse={14}>{aenderungsSatz}</Fliesstext>
      <dl className="grid grid-cols-1 gap-x-3 gap-y-3 sm:grid-cols-2" aria-label="Freigabe-Waage">
        <Waagschale titel="Bestand vorher" wert={formatZahl(vorher)} />
        <Waagschale titel="Bestand nachher" wert={formatZahl(nachher)} ton="gruen" />
        <Waagschale titel="Unterschied" wert={formatDifferenz(differenz)} art="zeile" />
        {prozent === null ? (
          <Waagschale titel="Unterschied in Prozent" wert="nicht berechenbar, vorher 0" art="zeile" />
        ) : (
          <Waagschale titel="Unterschied in Prozent" wert={formatProzent(prozent)} art="zeile" />
        )}
      </dl>

      {beleg && <HerkunftChip {...beleg} />}

      {hatDetails && (
        <details>
          <summary className={klassen("cursor-pointer font-sans text-14 font-semibold text-gruen", fokus)}>
            Details zum Vorschlag
          </summary>
          <div className="flex flex-col gap-4 pt-4">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 font-sans text-14">
              {eintrag.ref && (
                <>
                  <dt className="text-slate">Vorschlag</dt>
                  <dd className="font-mono text-ink">{eintrag.ref}</dd>
                </>
              )}
              {eintrag.wirkung && (
                <>
                  <dt className="text-slate">Wirkung</dt>
                  <dd className="text-ink">{eintrag.wirkung}</dd>
                </>
              )}
            </dl>
            {!diff && <Fliesstext groesse={14} ton="gedaempft">Keine Regeländerung hinterlegt.</Fliesstext>}
          </div>
        </details>
      )}

      {!entschieden && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-2">
            <label htmlFor={nameFeldId} className="font-sans text-14 font-semibold text-ink">
              Vor- und Nachname
            </label>
            <div className="flex flex-wrap items-start gap-3 sm:flex-nowrap">
              <input
                id={nameFeldId}
                name="freigabe-name"
                type="text"
                autoComplete="off"
                required
                aria-invalid={nameFehler ? true : undefined}
                aria-describedby={[nameHinweisId, nameFehler && nameFehlerId].filter(Boolean).join(" ")}
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={enterSperren}
                className={klassen(
                  "h-10 min-w-0 flex-1 basis-60 rounded-lg border bg-white px-3 font-sans text-14 text-ink",
                  nameFehler ? "border-err-fg" : "border-slate",
                  fokus,
                )}
              />
              {!ablehnen && (
                <Knopf disabled={!pruefung.gueltig || laeuft} onClick={() => void ausfuehren("freigegeben")}>
                  <Piktogramm name="haken" />
                  Freigeben
                </Knopf>
              )}
            </div>
            <p id={nameHinweisId} className="font-sans text-12 text-slate">
              {NAME_HINWEIS}
            </p>
            {nameFehler && (
              <Status id={nameFehlerId} art="fehler">
                {nameFehler}
              </Status>
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
              onChange={(e) => setBegruendung(e.target.value)}
              onKeyDown={enterSperren}
            />
          )}
          <div className="flex flex-wrap items-center gap-6">
            {ablehnen ? (
              <>
                <Knopf
                  art="sekundaer"
                  disabled={!pruefung.gueltig || !begruendung.trim() || laeuft}
                  onClick={() => void ausfuehren("abgelehnt")}
                >
                  Ablehnung speichern
                </Knopf>
                <button
                  type="button"
                  className={klassen("font-sans text-14 font-semibold text-ink underline underline-offset-4", fokus)}
                  onClick={() => wechsleAblehnen(false)}
                  disabled={laeuft}
                >
                  Zurück
                </button>
              </>
            ) : (
              <button
                id={ablehnenId}
                type="button"
                className={klassen("font-sans text-14 font-semibold text-ink underline underline-offset-4", fokus)}
                onClick={() => wechsleAblehnen(true)}
                disabled={laeuft}
              >
                Ablehnen
              </button>
            )}
          </div>
        </div>
      )}
      {/* Die Live-Region steht von Anfang an (leer); Screenreader melden nur Änderungen in einer Region, die schon
          da war. Ergebnis, Speichern und Fehler werden hier eingesetzt. tabIndex -1: nach einem Ergebnis setzt die
          Karte den Fokus hierher, die Tab-Folge bleibt gleich. Leer nimmt sie über `empty:-mt-4`
          keinen Platz ein, ohne aus dem Baum zu verschwinden (display: none würde die Ansage verschlucken). */}
      <div
        id={freigabeId}
        tabIndex={-1}
        aria-live="polite"
        data-meldung="freigabe"
        className={klassen("flex flex-col gap-2 empty:-mt-4", fokus)}
      >
        {entschieden ? (
          entschieden.art === "freigegeben" ? (
            <Status art="ok">{`Freigegeben von ${entschieden.name}, ${formatZeit(entschieden.zeit)}`}</Status>
          ) : (
            <>
              <Status art="info">{`Abgelehnt von ${entschieden.name}, ${formatZeit(entschieden.zeit)}`}</Status>
              <Fliesstext groesse={14}>{`Begründung: ${entschieden.begruendung}`}</Fliesstext>
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
    </article>
  );
}
