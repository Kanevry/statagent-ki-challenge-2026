"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Feld, Knopf, Status } from "@kic/ui/basis";
import { formatZeit, pruefeName, type FreigabeEntscheidung } from "@kic/ui/bausteine";
import { StandPunkt } from "@/components/uc3/beleg-link";

// Freigabe-Block eines Vorschlags (UI-Regie v1): entschieden ein Satz mit Name und Zeit, offen und lokal das
// Formular mit Vor- und Nachnamen, online (nurLesen) ein Satz ohne Knopf. Schickt Name (und Begründung) an
// POST /api/uc3/freigabe und lädt danach die Seite neu, damit Ergebnis und Link zum Monat aus der Datenbank kommen.
// Namensprüfung wie in der FreigabeKarte (pruefeName); die Knöpfe bleiben aktiv und sagen beim Klick, was fehlt.

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
  entscheidung?: FreigabeEntscheidung;
  /** Zeit der Entscheidung in Wiener Zeit, vom Server gesetzt („05.11. 16:53“; freigabe.ts ist nur serverseitig). */
  entschiedenAm?: string;
  /** Online-Demo (KIC_ONLINE_LESEND=1): nur ansehen, ohne Namensfeld und ohne Knopf. */
  nurLesen?: boolean;
};

const textKnopf =
  "inline-flex min-h-11 items-center font-sans text-14 font-medium text-ink underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy";

/** „Freigegeben von Erika Muster am 05.11. um 16:53.“ */
function EntschiedenSatz({ e, zeitText }: { e: FreigabeEntscheidung; zeitText?: string }) {
  const zeit = zeitText ?? formatZeit(e.zeit);
  const [tag = zeit, uhr] = zeit.replace(",", "").split(" ");
  return (
    <div className="flex flex-col gap-2">
      <StandPunkt stand={e.art} />
      <p className="font-sans text-20 text-ink">
        {`${e.art === "freigegeben" ? "Freigegeben" : "Abgelehnt"} von ${e.name} am `}
        <time dateTime={e.zeit} className="tabular-nums">
          {uhr ? `${tag} um ${uhr}` : tag}
        </time>
        .
      </p>
      {e.art === "abgelehnt" && e.begruendung && (
        <p className="font-sans text-16 text-ink">{`Begründung: ${e.begruendung}`}</p>
      )}
    </div>
  );
}

export function Entscheiden({ vorschlagId, entscheidung, entschiedenAm, nurLesen = false }: EntscheidenProps) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [ablehnen, setAblehnen] = useState(false);
  const [begruendung, setBegruendung] = useState("");
  const [laeuft, setLaeuft] = useState(false);
  const [hinweis, setHinweis] = useState<{ name?: string; begruendung?: string }>({});
  const [fehler, setFehler] = useState<string | null>(null);
  const [ergebnis, setErgebnis] = useState<FreigabeEntscheidung | null>(null);
  const [nichtAngewendet, setNichtAngewendet] = useState(false);
  // Fokus nach dem Umschalten (nicht beim ersten Laden): Ablehnen → Begründung, Zurück → Knopf „Ablehnen“.
  const [fokusZiel, setFokusZiel] = useState<"begruendung" | "ablehnen" | null>(null);
  const formular = useRef<HTMLFormElement>(null);
  const ablehnenKnopf = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (fokusZiel === "begruendung") {
      formular.current?.querySelector<HTMLInputElement>('[name="freigabe-begruendung"]')?.focus();
    } else if (fokusZiel === "ablehnen") {
      ablehnenKnopf.current?.focus();
    }
    if (fokusZiel) setFokusZiel(null);
  }, [fokusZiel]);

  const entschieden = entscheidung ?? ergebnis;

  if (entschieden) {
    return (
      <div aria-live="polite" className="flex flex-col gap-3">
        <EntschiedenSatz e={entschieden} zeitText={entscheidung ? entschiedenAm : undefined} />
        {nichtAngewendet && (
          <Status art="warnung">
            Die Freigabe ist gespeichert, die Regel ist aber noch nicht aktiv. Das Anwenden lässt sich wiederholen.
          </Status>
        )}
      </div>
    );
  }

  if (nurLesen) {
    return (
      <div className="flex flex-col gap-2">
        <StandPunkt stand="offen" />
        <p className="font-sans text-16 text-ink">
          Freigeben geht nur in der lokalen Anwendung, mit Vor- und Nachnamen. Online ist diese Seite nur zum Ansehen.
        </p>
      </div>
    );
  }

  function enterSperren(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") e.preventDefault();
  }

  async function ausfuehren(art: FreigabeEntscheidung["art"]) {
    if (laeuft) return;
    const pruefung = pruefeName(name);
    const grund = begruendung.trim();
    const neu: { name?: string; begruendung?: string } = {};
    if (!pruefung.gueltig) neu.name = name.trim() ? pruefung.grund : "Bitte Vor- und Nachnamen eintragen.";
    if (art === "abgelehnt" && !grund) neu.begruendung = "Bitte kurz sagen, warum Sie ablehnen.";
    setHinweis(neu);
    if (!pruefung.gueltig || (art === "abgelehnt" && !grund)) return;
    setLaeuft(true);
    setFehler(null);
    try {
      const daten = await senden(
        art === "freigegeben"
          ? { id: vorschlagId, name: pruefung.name, entscheidung: "ja" }
          : { id: vorschlagId, name: pruefung.name, entscheidung: "nein", begruendung: grund },
      );
      if (daten.angewendet === false) setNichtAngewendet(true);
      const zeit = daten.zeitpunkt ?? new Date().toISOString();
      setErgebnis(
        art === "freigegeben" ? { art, name: pruefung.name, zeit } : { art, name: pruefung.name, zeit, begruendung: grund },
      );
      router.refresh();
    } catch (e) {
      const meldung = e instanceof Error ? e.message.trim() : "";
      setFehler(meldung ? `Nicht gespeichert. ${meldung}` : "Nicht gespeichert. Bitte noch einmal versuchen.");
    } finally {
      setLaeuft(false);
    }
  }

  function absenden(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
  }

  return (
    <form
      ref={formular}
      onSubmit={absenden}
      className="flex max-w-xl flex-col gap-4"
      aria-label="Freigabe mit Vor- und Nachnamen"
      data-baustein="freigabe"
      data-zustand="offen"
    >
      <Feld
        label="Vor- und Nachname"
        name="freigabe-name"
        autoComplete="off"
        required
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={enterSperren}
        hinweis="Ihr Name und die Uhrzeit stehen danach im Protokoll."
        fehler={hinweis.name}
      />
      {ablehnen && (
        <Feld
          label="Warum lehnen Sie ab?"
          name="freigabe-begruendung"
          autoComplete="off"
          required
          maxLength={500}
          value={begruendung}
          onChange={(e) => setBegruendung(e.target.value)}
          onKeyDown={enterSperren}
          fehler={hinweis.begruendung}
        />
      )}
      <div className="flex flex-wrap items-center gap-6">
        {ablehnen ? (
          <>
            <Knopf art="sekundaer" aria-busy={laeuft} onClick={() => void ausfuehren("abgelehnt")}>
              Ablehnung speichern
            </Knopf>
            <button
              type="button"
              className={textKnopf}
              onClick={() => {
                setAblehnen(false);
                setHinweis({});
                setFokusZiel("ablehnen");
              }}
            >
              Zurück
            </button>
          </>
        ) : (
          <>
            <Knopf aria-busy={laeuft} onClick={() => void ausfuehren("freigegeben")}>
              Ja, so rechnen wir ab jetzt
            </Knopf>
            <button
              ref={ablehnenKnopf}
              type="button"
              className={textKnopf}
              onClick={() => {
                setAblehnen(true);
                setFokusZiel("begruendung");
              }}
            >
              Ablehnen
            </button>
          </>
        )}
      </div>
      <div aria-live="polite">
        {laeuft ? (
          <p className="font-sans text-14 text-slate">Wird gespeichert …</p>
        ) : fehler ? (
          <Status art="fehler" role="alert">
            {fehler}
          </Status>
        ) : null}
      </div>
    </form>
  );
}
