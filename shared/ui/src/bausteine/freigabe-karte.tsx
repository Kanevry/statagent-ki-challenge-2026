"use client";

import { useId, useState, type KeyboardEvent, type ReactNode } from "react";
import { Feld, Fliesstext, Knopf, Status, Ueberschrift } from "../basis";
import { fokus, klassen } from "../basis/klassen";
import { formatDifferenz, formatProzent, formatZahl, formatZeit, veraenderung } from "./format";
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
  /** Erhält den geprüften, getrimmten Namen. Ein abgelehntes Promise zeigt den Fehler an. */
  onFreigeben: (name: string) => void | Promise<void>;
  onAblehnen: (name: string, begruendung: string) => void | Promise<void>;
  /** Schon entschieden, z. B. aus dem Protokoll: Zone 3 zeigt dann das Ergebnis statt der Eingabe. */
  entscheidung?: FreigabeEntscheidung;
  /** Ebene der Zonen-Überschriften im Seitenaufbau. */
  ebene?: "h2" | "h3" | "h4";
  className?: string;
};

const ZONE_GESAGT = "Das wurde gesagt";
const ZONE_AENDERUNG = "Das ändert sich";
const ZONE_FREIGABE = "Freigabe mit Vor- und Nachname";

function fehlertext(fehler: unknown): string {
  const meldung = fehler instanceof Error ? fehler.message.trim() : "";
  return meldung ? `Nicht gespeichert. ${meldung}` : "Nicht gespeichert. Bitte noch einmal versuchen.";
}

function Zone({ id, titel, ebene, children }: { id: string; titel: string; ebene: "h2" | "h3" | "h4"; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-4 border-t border-line pt-6 first:border-t-0 first:pt-0">
      <Ueberschrift stufe={3} als={ebene} id={id}>
        {titel}
      </Ueberschrift>
      {children}
    </section>
  );
}

function Waagschale({ titel, wert, gross = true }: { titel: string; wert: string; gross?: boolean }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="font-sans text-14 text-slate">{titel}</dt>
      <dd className={klassen("font-mono tabular-nums text-ink", gross ? "text-56" : "text-20")}>{wert}</dd>
    </div>
  );
}

function Diff({ text }: { text: string }) {
  return (
    <pre className="max-w-full overflow-x-auto rounded border border-line bg-paper p-2 font-mono text-12 text-ink">
      {text.split("\n").map((zeile, index) => (
        <span
          key={index}
          className={klassen(
            "block",
            zeile.startsWith("+") && "bg-gruen-bg",
            zeile.startsWith("-") && "bg-err-bg",
          )}
        >
          {zeile || " "}
        </span>
      ))}
    </pre>
  );
}

/**
 * Freigabe einer Änderung in drei festen Zonen: was gesagt wurde, was sich ändert, wer freigibt.
 * Der Knopf wird erst bei gültigem Vor- und Nachnamen aktiv; Enter im Namensfeld löst nichts aus.
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
  entscheidung,
  ebene = "h3",
  className,
}: FreigabeKarteProps) {
  const basisId = useId();
  const [name, setName] = useState("");
  const [nameVerlassen, setNameVerlassen] = useState(false);
  const [ablehnen, setAblehnen] = useState(false);
  const [begruendung, setBegruendung] = useState("");
  const [laeuft, setLaeuft] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [ergebnis, setErgebnis] = useState<FreigabeEntscheidung | null>(null);

  const pruefung = pruefeName(name);
  const entschieden = entscheidung ?? ergebnis;
  const { differenz, prozent } = veraenderung(vorher, nachher);
  const einheit = groesse ? ` ${groesse}` : "";
  const aenderungsSatz =
    satz ??
    (differenz === 0
      ? `Die Zahl bleibt bei ${formatZahl(vorher)}${einheit}.`
      : `Ab jetzt zählen wir ${formatZahl(nachher)}${einheit} statt ${formatZahl(vorher)}.`);
  const zone3Titel =
    entschieden?.art === "freigegeben" ? "Freigegeben" : entschieden?.art === "abgelehnt" ? "Abgelehnt" : ZONE_FREIGABE;

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
        await onFreigeben(pruefung.name);
        setErgebnis({ art, name: pruefung.name, zeit: new Date().toISOString() });
      } else {
        await onAblehnen(pruefung.name, grund);
        setErgebnis({ art, name: pruefung.name, zeit: new Date().toISOString(), begruendung: grund });
      }
    } catch (e) {
      setFehler(fehlertext(e));
    } finally {
      setLaeuft(false);
    }
  }

  return (
    <article
      className={klassen("flex flex-col gap-6 rounded border border-line bg-white p-6", className)}
      data-baustein="freigabe"
      data-zustand={entschieden?.art ?? "offen"}
    >
      <Zone id={`${basisId}-gesagt`} titel={ZONE_GESAGT} ebene={ebene}>
        <blockquote className="border-l-2 border-line pl-4">
          <Fliesstext>{`„${eintrag.anweisung}“`}</Fliesstext>
        </blockquote>
        <Fliesstext groesse={14} ton="gedaempft">
          {eintrag.name}
          {" · "}
          <time dateTime={eintrag.zeit}>{formatZeit(eintrag.zeit)}</time>
        </Fliesstext>
      </Zone>

      <Zone id={`${basisId}-aenderung`} titel={ZONE_AENDERUNG} ebene={ebene}>
        <Fliesstext>{aenderungsSatz}</Fliesstext>
        <dl className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2" aria-label="Freigabe-Waage">
          <Waagschale titel="Vorher" wert={formatZahl(vorher)} />
          <Waagschale titel="Nachher" wert={formatZahl(nachher)} />
          <Waagschale titel="Δ Unterschied" wert={formatDifferenz(differenz)} />
          {prozent === null ? (
            <Waagschale titel="Δ in Prozent" wert="nicht berechenbar, vorher 0" gross={false} />
          ) : (
            <Waagschale titel="Δ in Prozent" wert={formatProzent(prozent)} />
          )}
        </dl>
        <details>
          <summary className={klassen("cursor-pointer font-sans text-14 font-semibold text-gruen", fokus)}>
            Details und Regeländerung
          </summary>
          <div className="flex flex-col gap-4 pt-4">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 font-sans text-14">
              {eintrag.ref && (
                <>
                  <dt className="text-slate">Vorschlag</dt>
                  <dd className="font-mono text-ink">{eintrag.ref}</dd>
                </>
              )}
              {eintrag.modell && (
                <>
                  <dt className="text-slate">Modell</dt>
                  <dd className="font-mono text-ink">{eintrag.modell}</dd>
                </>
              )}
              {eintrag.wirkung && (
                <>
                  <dt className="text-slate">Wirkung</dt>
                  <dd className="text-ink">{eintrag.wirkung}</dd>
                </>
              )}
            </dl>
            {diff ? <Diff text={diff} /> : <Fliesstext groesse={14} ton="gedaempft">Kein Diff hinterlegt.</Fliesstext>}
          </div>
        </details>
      </Zone>

      <Zone id={`${basisId}-freigabe`} titel={zone3Titel} ebene={ebene}>
        {entschieden ? (
          <div className="flex flex-col gap-2" role="status">
            {entschieden.art === "freigegeben" ? (
              <Status art="ok">{`Freigegeben von ${entschieden.name}, ${formatZeit(entschieden.zeit)}`}</Status>
            ) : (
              <>
                <Status art="info">{`Abgelehnt von ${entschieden.name}, ${formatZeit(entschieden.zeit)}`}</Status>
                <Fliesstext groesse={14}>{`Begründung: ${entschieden.begruendung}`}</Fliesstext>
              </>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <Fliesstext>Wer gibt frei? Ihr Name kommt ins Protokoll und in den Commit.</Fliesstext>
            <Feld
              label="Vor- und Nachname"
              name="freigabe-name"
              autoComplete="off"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={() => setNameVerlassen(true)}
              onKeyDown={enterSperren}
              hinweis="Zum Beispiel Anna Beispiel. Rollen wie „Team“ zählen nicht."
              fehler={nameVerlassen && name.trim() && !pruefung.gueltig ? pruefung.grund : undefined}
            />
            {ablehnen && (
              <Feld
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
                    onClick={() => setAblehnen(false)}
                    disabled={laeuft}
                  >
                    Zurück
                  </button>
                </>
              ) : (
                <>
                  <Knopf disabled={!pruefung.gueltig || laeuft} onClick={() => void ausfuehren("freigegeben")}>
                    Ja, so rechnen wir ab jetzt
                  </Knopf>
                  <button
                    type="button"
                    className={klassen("font-sans text-14 font-semibold text-ink underline underline-offset-4", fokus)}
                    onClick={() => setAblehnen(true)}
                    disabled={laeuft}
                  >
                    Ablehnen
                  </button>
                </>
              )}
            </div>
            <div aria-live="polite">
              {laeuft && <Status art="info">Wird gespeichert</Status>}
              {fehler && (
                <Status art="fehler" role="alert">
                  {fehler}
                </Status>
              )}
            </div>
          </div>
        )}
      </Zone>
    </article>
  );
}
