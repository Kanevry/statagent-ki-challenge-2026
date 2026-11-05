"use client";

import { useRouter } from "next/navigation";
import { useId, useState, type KeyboardEvent, type ReactNode } from "react";
import { Feld, Fliesstext, Knopf, Status, Ueberschrift } from "@kic/ui/basis";
import {
  FreigabeKarte,
  formatZeit,
  pruefeName,
  type FreigabeAntwort,
  type FreigabeEintrag,
  type FreigabeEntscheidung,
  type HerkunftChipProps,
} from "@kic/ui/bausteine";

// Entscheidung über einen Vorschlag: schickt Name (und Begründung) an POST /api/uc3/freigabe und lädt danach die
// Seite neu, damit Ergebnis und Link zum Monat aus der Datenbank kommen. Mit gerechneter Probe die FreigabeKarte
// (Waage); ohne Probe dieselben drei Zonen ohne Zahlen, weil die Freigabe nicht von der Probe abhängt.

type Antwort = { zeitpunkt?: string | null; angewendet?: boolean; fehler?: string; grund?: string };

async function senden(body: Record<string, unknown>): Promise<Antwort> {
  let antwort: Response;
  try {
    antwort = await fetch("/api/uc3/freigabe", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Der Server ist nicht erreichbar. Bitte noch einmal versuchen.");
  }
  const daten = (await antwort.json().catch(() => ({}))) as Antwort;
  if (!antwort.ok) throw new Error(daten.grund ?? daten.fehler ?? "Bitte noch einmal versuchen.");
  return daten;
}

export type EntscheidenProps = {
  vorschlagId: number;
  eintrag: FreigabeEintrag;
  /** Mit Probe: Zahlen der Waage. Ohne: null, dann steht `ohneProbe` in Zone 2. */
  zahlen: { vorher: number; nachher: number; satz: string; beleg: Omit<HerkunftChipProps, "className"> } | null;
  diff: string;
  /** Inhalt der Zone 2 ohne Probe (Satz, Hinweis, Regeländerung in Worten). */
  ohneProbe: ReactNode;
  entscheidung?: FreigabeEntscheidung;
};

export function Entscheiden({ vorschlagId, eintrag, zahlen, diff, ohneProbe, entscheidung }: EntscheidenProps) {
  const router = useRouter();
  const [nichtAngewendet, setNichtAngewendet] = useState(false);

  async function entscheiden(body: Record<string, unknown>): Promise<FreigabeAntwort> {
    const daten = await senden({ id: vorschlagId, ...body });
    if (daten.angewendet === false) setNichtAngewendet(true);
    router.refresh();
    return { zeitpunkt: daten.zeitpunkt ?? null };
  }
  const onFreigeben = (name: string) => entscheiden({ name, entscheidung: "ja" });
  const onAblehnen = (name: string, begruendung: string) => entscheiden({ name, entscheidung: "nein", begruendung });

  return (
    <div className="flex flex-col gap-4">
      {zahlen ? (
        <FreigabeKarte
          eintrag={eintrag}
          vorher={zahlen.vorher}
          nachher={zahlen.nachher}
          satz={zahlen.satz}
          diff={diff}
          beleg={zahlen.beleg}
          onFreigeben={onFreigeben}
          onAblehnen={onAblehnen}
          entscheidung={entscheidung}
          ebene="h2"
        />
      ) : (
        <KarteOhneProbe
          eintrag={eintrag}
          onFreigeben={onFreigeben}
          onAblehnen={onAblehnen}
          entscheidung={entscheidung}
        >
          {ohneProbe}
        </KarteOhneProbe>
      )}
      {nichtAngewendet && (
        <Status art="warnung">
          Die Freigabe ist gespeichert, die Regel ist aber noch nicht aktiv. Das Anwenden lässt sich wiederholen.
        </Status>
      )}
    </div>
  );
}

const unterstrichen =
  "font-sans text-14 font-semibold text-ink underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy";

function Zone({ titel, children }: { titel: string; children: ReactNode }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="flex flex-col gap-4 border-t border-line pt-6 first:border-t-0 first:pt-0">
      <Ueberschrift stufe={3} als="h2" id={id} tabIndex={-1}>
        {titel}
      </Ueberschrift>
      {children}
    </section>
  );
}

/** Dieselben drei Zonen wie die FreigabeKarte, Zone 2 ohne Waage. Name-Regel und Enter-Sperre wie in der Karte. */
function KarteOhneProbe({
  eintrag,
  onFreigeben,
  onAblehnen,
  entscheidung,
  children,
}: {
  eintrag: FreigabeEintrag;
  onFreigeben: (name: string) => Promise<FreigabeAntwort>;
  onAblehnen: (name: string, begruendung: string) => Promise<FreigabeAntwort>;
  entscheidung?: FreigabeEntscheidung;
  children: ReactNode;
}) {
  const [name, setName] = useState("");
  const [verlassen, setVerlassen] = useState(false);
  const [ablehnen, setAblehnen] = useState(false);
  const [begruendung, setBegruendung] = useState("");
  const [laeuft, setLaeuft] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [ergebnis, setErgebnis] = useState<FreigabeEntscheidung | null>(null);
  const pruefung = pruefeName(name);
  const entschieden = entscheidung ?? ergebnis;

  function enterSperren(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") e.preventDefault();
  }

  async function ausfuehren(art: FreigabeEntscheidung["art"]) {
    const grund = begruendung.trim();
    if (!pruefung.gueltig || laeuft || (art === "abgelehnt" && !grund)) return;
    setLaeuft(true);
    setFehler(null);
    try {
      const antwort = art === "freigegeben" ? await onFreigeben(pruefung.name) : await onAblehnen(pruefung.name, grund);
      const zeit = (antwort as { zeitpunkt?: string | null } | undefined)?.zeitpunkt ?? new Date().toISOString();
      setErgebnis(
        art === "freigegeben"
          ? { art, name: pruefung.name, zeit }
          : { art, name: pruefung.name, zeit, begruendung: grund },
      );
    } catch (e) {
      const meldung = e instanceof Error ? e.message.trim() : "";
      setFehler(meldung ? `Nicht gespeichert. ${meldung}` : "Nicht gespeichert. Bitte noch einmal versuchen.");
    } finally {
      setLaeuft(false);
    }
  }

  return (
    <article
      className="flex flex-col gap-6 rounded border border-line bg-white p-6"
      data-baustein="freigabe"
      data-zustand={entschieden?.art ?? "offen"}
    >
      <Zone titel="Das wurde gesagt">
        <blockquote className="border-l-2 border-line pl-4">
          <Fliesstext>{`„${eintrag.anweisung}“`}</Fliesstext>
        </blockquote>
        <Fliesstext groesse={14} ton="gedaempft">
          {eintrag.name}
          {" · "}
          <time dateTime={eintrag.zeit}>{formatZeit(eintrag.zeit)}</time>
        </Fliesstext>
      </Zone>

      <Zone titel="Das ändert sich">{children}</Zone>

      <Zone
        titel={
          entschieden?.art === "freigegeben" ? "Freigegeben" : entschieden?.art === "abgelehnt" ? "Abgelehnt" : "Freigabe mit Vor- und Nachname"
        }
      >
        {!entschieden && (
          <div className="flex flex-col gap-4">
            <Feld
              label="Vor- und Nachname"
              name="freigabe-name"
              autoComplete="off"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={() => setVerlassen(true)}
              onKeyDown={enterSperren}
              hinweis="Ihr Name und die Uhrzeit werden im Protokoll gespeichert."
              fehler={verlassen && name.trim() && !pruefung.gueltig ? pruefung.grund : undefined}
            />
            {ablehnen && (
              <Feld
                label="Begründung der Ablehnung"
                name="freigabe-begruendung"
                autoComplete="off"
                required
                maxLength={500}
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
                  <button type="button" className={unterstrichen} onClick={() => setAblehnen(false)} disabled={laeuft}>
                    Zurück
                  </button>
                </>
              ) : (
                <>
                  <Knopf disabled={!pruefung.gueltig || laeuft} onClick={() => void ausfuehren("freigegeben")}>
                    Ja, so rechnen wir ab jetzt
                  </Knopf>
                  <button type="button" className={unterstrichen} onClick={() => setAblehnen(true)} disabled={laeuft}>
                    Ablehnen
                  </button>
                </>
              )}
            </div>
          </div>
        )}
        <div aria-live="polite" className="flex flex-col gap-2">
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
      </Zone>
    </article>
  );
}
