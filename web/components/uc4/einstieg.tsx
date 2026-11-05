"use client";

import { useState, type FormEvent } from "react";
import { Feld, Fliesstext, Knopf, Status, Ueberschrift, Zahl } from "@kic/ui/basis";
import { HerkunftChip } from "@kic/ui/bausteine";
import { findeUc } from "@kic/ui/ucs";
import type { UcAntwort } from "@kic/ui/antwortform";
import {
  ergebnisSchema,
  frageSchema,
  grundText,
  KETTE,
  MAX_FRAGE,
  type Ergebnis,
  type Fehlend,
  type KettenUc,
} from "../../lib/plattform/uc4-ergebnis";

// Gemeinsamer Einstieg (#98): Frage-Feld, darunter je UC der Kette eine Karte. Eine Anfrage liefert alle drei
// Antworten auf einmal; Leer, Laden und Fehler gelten deshalb für alle Karten gleich, „fehlt“ je UC.
// Die Live-Region bleibt dauerhaft im DOM, damit Screenreader jeden Wechsel hören.

type Zustand =
  | { art: "leer" }
  | { art: "laden" }
  | { art: "ok"; ergebnis: Ergebnis }
  | { art: "fehler"; meldung: string };

const GESPERRT = "Fragen sind in der Online-Demo noch gesperrt.";

/** Was die Karte zur Herkunft ihres Kontexts sagt: Schritt 1 sieht nur die Frage. */
function kontextSatz(stelle: number): string {
  if (stelle === 0) return "Bekommt die Frage.";
  const davor = KETTE.slice(0, stelle).map((uc) => findeUc(uc).name);
  return `Bekommt die Frage und die Antwort von ${davor.join(" und ")}.`;
}

/** Felder eines Belegs, die der Chip zeigt; passt auf die Antwortform vor und nach Review !30. */
type BelegAnsicht = {
  quelle: string;
  lieferung?: string | null;
  sql?: string | null;
  ref?: string | null;
  lauf?: string | null;
  stand?: "endgueltig" | "vorlaeufig" | null;
};

function Zahlen({ antwort }: { antwort: UcAntwort }) {
  if (antwort.zahlen.length === 0) return null;
  return (
    <ul className="flex flex-col gap-4 border-t border-line pt-4">
      {antwort.zahlen.map((zahl, nummer) => {
        const beleg: BelegAnsicht | undefined = antwort.belege[zahl.beleg];
        return (
          <li key={`${zahl.bezeichnung}-${nummer}`} className="flex flex-col items-start gap-2" data-zahl="">
            <p className="flex flex-wrap items-baseline gap-2 font-sans text-14 text-slate">
              <span>{zahl.bezeichnung}</span>
              <Zahl wert={zahl.wert} einheit={zahl.einheit ?? undefined} className="text-20 font-semibold text-ink" />
            </p>
            {beleg && (
              <HerkunftChip
                quelle={beleg.quelle}
                lieferung={beleg.lieferung}
                sql={beleg.sql}
                lauf={beleg.lauf}
                verweis={beleg.ref}
                stand={beleg.stand}
              />
            )}
          </li>
        );
      })}
    </ul>
  );
}

function Modell({ modell }: { modell: string | null | undefined }) {
  return (
    <p className="inline-flex items-center gap-2 border-l-2 border-violett pl-2 font-sans text-12" data-testid="uc4-modell">
      <span className="text-slate">Modell</span>
      <span className={modell ? "font-mono text-ink" : "text-slate"}>{modell ?? "keins, gerechnet von Code"}</span>
    </p>
  );
}

function KartenInhalt({ uc, zustand }: { uc: KettenUc; zustand: Zustand }) {
  const name = findeUc(uc).name;
  if (zustand.art === "leer") {
    return <Fliesstext ton="gedaempft">{`${name} antwortet, sobald eine Frage gestellt ist.`}</Fliesstext>;
  }
  if (zustand.art === "laden") {
    return <Fliesstext ton="gedaempft">{`${name} wartet auf seinen Schritt in der Kette.`}</Fliesstext>;
  }
  if (zustand.art === "fehler") {
    return <Status art="fehler">{zustand.meldung}</Status>;
  }
  const antwort = zustand.ergebnis.antworten.find((a) => a.uc === uc);
  if (!antwort) {
    const fehlt: Fehlend | undefined = zustand.ergebnis.fehlend.find((f) => f.uc === uc);
    return (
      <div className="flex flex-col items-start gap-2">
        <Status art="warnung">{fehlt ? grundText(fehlt.grund) : "Keine Antwort"}</Status>
        <Fliesstext groesse={14} ton="gedaempft">
          Die Kette lief ohne diesen Schritt weiter.
        </Fliesstext>
      </div>
    );
  }
  return (
    <>
      <Fliesstext>{antwort.text}</Fliesstext>
      <Zahlen antwort={antwort} />
      <Modell modell={antwort.modell} />
    </>
  );
}

function kartenZustand(uc: KettenUc, zustand: Zustand): string {
  if (zustand.art !== "ok") return zustand.art;
  return zustand.ergebnis.antworten.some((a) => a.uc === uc) ? "antwort" : "fehlt";
}

function ansage(zustand: Zustand): string {
  if (zustand.art === "leer") return "";
  if (zustand.art === "laden") return "Die Frage läuft durch die Kette.";
  if (zustand.art === "fehler") return zustand.meldung;
  const { antworten, fehlend } = zustand.ergebnis;
  const zahl = antworten.length === 1 ? "1 Antwort" : `${antworten.length} Antworten`;
  if (fehlend.length === 0) return `${zahl} da.`;
  return `${zahl} da, es fehlt ${fehlend.map((f) => findeUc(f.uc).name).join(" und ")}.`;
}

async function stelleFrage(frage: string): Promise<Zustand> {
  let antwort: Response;
  try {
    antwort = await fetch("/api/uc4/frage", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ frage }),
      cache: "no-store",
    });
  } catch {
    return { art: "fehler", meldung: "Keine Verbindung zum Server." };
  }
  // Sperrt der Proxy POST (403/405), gilt der Demo-Hinweis. 429 (Ratenlimit oder Tagesbudget, #100) bringt seinen
  // Hinweis im Feld `fehler` mit.
  if (antwort.status === 403 || antwort.status === 405) return { art: "fehler", meldung: GESPERRT };
  const daten: unknown = await antwort.json().catch(() => null);
  if (!antwort.ok) {
    const meldung =
      daten && typeof daten === "object" && "fehler" in daten && typeof daten.fehler === "string"
        ? daten.fehler
        : antwort.status === 429
          ? "Gerade sind zu viele Fragen unterwegs. Bitte später noch einmal fragen."
          : "Die Kette hat nicht geantwortet.";
    return { art: "fehler", meldung };
  }
  const geprueft = ergebnisSchema.safeParse(daten);
  return geprueft.success
    ? { art: "ok", ergebnis: geprueft.data }
    : { art: "fehler", meldung: "Die Antwort kam nicht im erwarteten Format." };
}

export function Einstieg() {
  const [frage, setFrage] = useState("");
  const [eingabeFehler, setEingabeFehler] = useState<string | undefined>();
  const [zustand, setZustand] = useState<Zustand>({ art: "leer" });
  const laedt = zustand.art === "laden";

  async function absenden(ereignis: FormEvent<HTMLFormElement>) {
    ereignis.preventDefault();
    if (laedt) return;
    const geprueft = frageSchema.safeParse({ frage });
    if (!geprueft.success) {
      setEingabeFehler(geprueft.error.issues[0]?.message);
      return;
    }
    setEingabeFehler(undefined);
    setZustand({ art: "laden" });
    setZustand(await stelleFrage(geprueft.data.frage));
  }

  return (
    <>
      <form onSubmit={absenden} className="flex max-w-3xl flex-col gap-4 sm:flex-row sm:items-start" noValidate>
        <Feld
          label="Frage an die Kette"
          hinweis={`Höchstens ${MAX_FRAGE} Zeichen. Enter schickt die Frage ab.`}
          fehler={eingabeFehler}
          name="frage"
          value={frage}
          maxLength={MAX_FRAGE}
          placeholder="Wie viele Beschäftigte gab es im März 2025?"
          onChange={(e) => setFrage(e.target.value)}
          className="flex-1"
        />
        <Knopf type="submit" disabled={laedt} className="sm:mt-7">
          {laedt ? "Frage läuft" : "Frage stellen"}
        </Knopf>
      </form>

      <p role="status" aria-live="polite" className="sr-only">
        {ansage(zustand)}
      </p>

      <section aria-label="Antworten in der Reihenfolge der Kette" aria-busy={laedt}>
        <ol className="grid gap-4 lg:grid-cols-3">
          {KETTE.map((uc, stelle) => (
            <li
              key={uc}
              data-uc-karte={uc}
              data-zustand={kartenZustand(uc, zustand)}
              className="flex flex-col gap-4 rounded border border-line bg-white p-4 md:p-6"
            >
              <div className="flex flex-col gap-1">
                <Ueberschrift stufe={3} als="h2">
                  {`${stelle + 1}. ${findeUc(uc).name}`}
                </Ueberschrift>
                <Fliesstext groesse={14} ton="gedaempft">
                  {kontextSatz(stelle)}
                </Fliesstext>
              </div>
              <KartenInhalt uc={uc} zustand={zustand} />
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}
