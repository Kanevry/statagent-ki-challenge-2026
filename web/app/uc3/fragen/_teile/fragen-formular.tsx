"use client";

import { useId, useRef, useState, type FormEvent } from "react";
import type { UcAntwort } from "@kic/ui/antwortform";
import { formatZahl } from "@kic/ui/bausteine";
import { Status } from "@kic/ui/basis";
import { BelegLink, StandPunkt } from "@/components/uc3/beleg-link";
import { alsCsv, istRueckfrage } from "@/components/uc3/antwort";
import {
  antwortTabelle,
  ersterSatz,
  istSummenzeile,
  kopfSagtVerstanden,
  kopfSatz,
  rueckfrageVorschlaege,
  teileBezeichnung,
  verstandenSatz,
} from "./antwort-ansicht";

export type Definition = { code: string; beschreibung: string };

type Ergebnis = {
  antwort: UcAntwort;
  definition: string | null;
  rueckfrage: string | null;
  quelle: "frage" | "antwort";
};

type Zustand =
  | { art: "leer" }
  | { art: "laedt" }
  | { art: "fehler"; satz: string }
  | { art: "fertig"; ergebnis: Ergebnis };

// Fragen an die Daten (UI-Regie v1): vor der ersten Frage füllen Feld und Knopf die Bühne, darunter vier Beispiele
// als schlichte Textzeilen. Die Antwort zeigt eine große Zahl, was das Programm verstanden hat, und die Abfrage als
// Beleg; Tabellen als schlichte Tabelle; eine Rückfrage als Frage mit Knöpfen für die Folgefrage. Online gesperrt
// (nurLesen) ein gestalteter Zustand ohne Feld und Knopf. API und Logik: components/uc3/antwort.ts, POST /api/uc3/frage.

// Je ein Beispiel für eine Zahl, eine Tabelle, eine Aufteilung und eine Rückfrage statt einer
// geratenen Zahl; alle am 05.11. gegen `uc3 frage --json` auf der UC3-Datenbank geprüft (Sichtprüfung bb, #18).
const BEISPIELE = [
  "Beschäftigte in Wien im Gesundheits- und Sozialwesen im März 2025",
  "Männer und Frauen im Oktober 2025 je Bundesland",
  // „Fluktuation je Wirtschaftsbereich“ entfällt: online fehlt bereinigt.abschnitt, die Frage scheiterte (Jury 05.11.).
  "Männer und Frauen in Tirol im Juli 2026",
  "Beschäftigte 2025",
] as const;

const FEHLERSATZ: Record<number, string> = {
  403: "Fragen an die Daten sind in der Online-Ansicht gesperrt.",
  415: "Die Seite hat die Frage in einer falschen Form geschickt. Bitte laden Sie die Seite neu.",
  413: "Die Frage ist zu lang. Bitte fragen Sie kürzer.",
  429: "Gerade rechnet das Programm schon zwei Fragen. Bitte fragen Sie gleich noch einmal.",
  502: "Das Programm konnte die Frage gerade nicht beantworten. Bitte fragen Sie gleich noch einmal.",
};

const textLink =
  "inline-flex min-h-11 items-center text-left font-sans text-14 text-slate underline decoration-line underline-offset-4 hover:text-ink hover:decoration-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen";

/** Definition aus der Antwort, sonst die Beschreibung der Variable, deren Code in einer Abfrage vorkommt. */
function definitionFuer(ergebnis: Ergebnis, definitionen: readonly Definition[]): string | null {
  if (ergebnis.definition) return ergebnis.definition;
  const sqls = ergebnis.antwort.belege.map((b) => b.sql ?? "");
  return definitionen.find((d) => sqls.some((sql) => sql.includes(`'${d.code}'`)))?.beschreibung ?? null;
}

function herunterladen(antwort: UcAntwort) {
  // BOM, damit Tabellenprogramme Umlaute als UTF-8 lesen.
  const blob = new Blob(["﻿", alsCsv(antwort)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "fragen-an-die-daten.csv";
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function zahlText(wert: number, einheit: string | null | undefined): string {
  const text = formatZahl(wert);
  if (einheit === "Prozent") return `${text} %`;
  return einheit && einheit !== "Anzahl" ? `${text} ${einheit}` : text;
}

export function FragenFormular({
  definitionen,
  nurLesen = false,
}: {
  definitionen: readonly Definition[];
  nurLesen?: boolean;
}) {
  const [frage, setFrage] = useState("");
  const [eingabeFehler, setEingabeFehler] = useState<string | undefined>();
  const [zustand, setZustand] = useState<Zustand>({ art: "leer" });
  const laufend = useRef<AbortController | null>(null);
  const feldId = useId();
  const fehlerId = `${feldId}-fehler`;

  async function senden(text: string) {
    const sauber = text.trim();
    if (!sauber) {
      setEingabeFehler("Bitte geben Sie eine Frage ein.");
      return;
    }
    setEingabeFehler(undefined);
    laufend.current?.abort();
    const abbruch = new AbortController();
    laufend.current = abbruch;
    setZustand({ art: "laedt" });
    try {
      const antwort = await fetch("/api/uc3/frage", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ frage: sauber }),
        signal: abbruch.signal,
      });
      const daten: unknown = await antwort.json().catch(() => null);
      if (abbruch.signal.aborted) return;
      if (antwort.ok && daten && typeof daten === "object" && "antwort" in daten) {
        setZustand({ art: "fertig", ergebnis: daten as Ergebnis });
        return;
      }
      const meldung = (daten as { fehler?: unknown } | null)?.fehler;
      const satz =
        antwort.status === 400 && typeof meldung === "string"
          ? meldung
          : (FEHLERSATZ[antwort.status] ?? FEHLERSATZ[502]!);
      setZustand({ art: "fehler", satz });
    } catch {
      if (abbruch.signal.aborted) return;
      setZustand({ art: "fehler", satz: "Die Seite hat keine Verbindung zum Programm. Bitte fragen Sie gleich noch einmal." });
    }
  }

  function fragen(text: string) {
    setFrage(text);
    void senden(text);
  }

  function absenden(ereignis: FormEvent<HTMLFormElement>) {
    ereignis.preventDefault();
    void senden(frage);
  }

  const buehne = zustand.art === "leer";

  if (nurLesen) {
    return (
      <div className="flex min-h-[60dvh] flex-col justify-center">
        <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 text-center">
          <h1 className="font-display text-32 font-bold text-balance text-ink">Fragen Sie die Daten in eigenen Worten.</h1>
          <p className="font-sans text-16 text-pretty text-slate">
            Online ist diese Seite gesperrt, weil jede Frage das Programm auf dem Server rechnen lässt. In der lokalen
            Anwendung stellen Sie hier Ihre Frage.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={buehne ? "flex min-h-[60dvh] flex-col justify-center" : "flex flex-col gap-10"}>
      <div className={`flex w-full max-w-2xl flex-col gap-6 ${buehne ? "mx-auto" : ""}`}>
        <div className={`flex flex-col gap-2 ${buehne ? "text-center" : ""}`}>
          <h1 className={`font-display font-bold text-balance text-ink ${buehne ? "text-32" : "text-20"}`}>
            Fragen Sie die Daten in eigenen Worten.
          </h1>
          {buehne && (
            <p className="font-sans text-16 text-pretty text-slate">
              Das Programm rechnet die Antwort ohne KI aus der Datenbank und zeigt die Abfrage dazu.
            </p>
          )}
        </div>

        <form onSubmit={absenden} className="flex flex-col gap-2" aria-label="Frage an die Daten">
          <label htmlFor={feldId} className="sr-only">
            Ihre Frage
          </label>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              id={feldId}
              name="frage"
              value={frage}
              maxLength={500}
              autoComplete="off"
              placeholder="Zum Beispiel: Beschäftigte in Wien im März 2025"
              aria-invalid={eingabeFehler ? true : undefined}
              aria-describedby={eingabeFehler ? fehlerId : undefined}
              onChange={(e) => setFrage(e.target.value)}
              className={`min-w-0 rounded-lg border bg-white sm:flex-1 px-4 font-sans text-ink placeholder:text-slate focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen ${
                eingabeFehler ? "border-err-fg" : "border-slate"
              } ${buehne ? "h-14 text-20" : "h-11 text-16"}`}
            />
            <button
              type="submit"
              aria-busy={zustand.art === "laedt"}
              className={`inline-flex items-center justify-center rounded-lg bg-gruen px-6 font-sans font-semibold text-white transition-colors hover:bg-gruen-dunkel focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen ${
                buehne ? "h-14 text-20" : "h-11 text-16"
              }`}
            >
              Fragen
            </button>
          </div>
          {eingabeFehler && (
            <Status id={fehlerId} art="fehler">
              {eingabeFehler}
            </Status>
          )}
        </form>

        {buehne && (
          <div className="flex flex-col">
            <p className="font-sans text-14 text-slate" id="beispiele-titel">
              Oder eines davon:
            </p>
            <ul aria-labelledby="beispiele-titel" className="flex flex-col gap-2 sm:gap-0">
              {BEISPIELE.map((beispiel) => (
                <li key={beispiel}>
                  <button type="button" onClick={() => fragen(beispiel)} className={`${textLink} text-16 text-ink`}>
                    {beispiel}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {!buehne && (
        <section aria-labelledby="ergebnis-titel" className="flex max-w-3xl flex-col gap-4">
          <h2 id="ergebnis-titel" className="sr-only">
            Antwort des Programms
          </h2>
          <div aria-live="polite" aria-busy={zustand.art === "laedt"} className="flex flex-col gap-4">
            {zustand.art === "laedt" && <p className="font-sans text-16 text-slate">Das Programm rechnet …</p>}
            {zustand.art === "fehler" && <Status art="fehler">{zustand.satz}</Status>}
            {zustand.art === "fertig" && (
              <Antwort ergebnis={zustand.ergebnis} definitionen={definitionen} onFolgefrage={fragen} />
            )}
          </div>
          {zustand.art !== "laedt" && (
            <div className="flex flex-col border-t border-line pt-4">
              <p className="font-sans text-14 text-slate" id="noch-eine-frage">
                Noch eine Frage:
              </p>
              <ul aria-labelledby="noch-eine-frage" className="flex flex-col gap-2 sm:gap-0">
                {BEISPIELE.filter((b) => b !== frage.trim()).map((beispiel) => (
                  <li key={beispiel}>
                    <button type="button" onClick={() => fragen(beispiel)} className={`${textLink} text-16 text-ink`}>
                      {beispiel}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function Antwort({
  ergebnis,
  definitionen,
  onFolgefrage,
}: {
  ergebnis: Ergebnis;
  definitionen: readonly Definition[];
  onFolgefrage: (frage: string) => void;
}) {
  const { antwort, rueckfrage } = ergebnis;

  if (istRueckfrage(antwort, rueckfrage)) {
    const text = rueckfrage ?? antwort.text;
    // Eine Erklärung nennt Namen in Anführungszeichen; als Knopf taugt nur eine Frage oder ein Beispiel mit Zeitangabe (#189).
    const vorschlaege = rueckfrageVorschlaege(text).filter((v) => rueckfrage !== null || v.endsWith("?") || /\b20\d{2}\b/.test(v));
    return (
      <div className="flex flex-col gap-4">
        <p className="font-sans text-20 text-pretty text-ink">{text}</p>
        {vorschlaege.length > 0 ? (
          <div className="flex flex-wrap gap-3">
            {vorschlaege.map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => onFolgefrage(v)}
                className="inline-flex min-h-11 items-center rounded-lg border border-gruen px-4 font-sans text-16 font-semibold text-gruen hover:bg-gruen-bg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen"
              >
                {v}
              </button>
            ))}
          </div>
        ) : (
          // Nur bei einer echten Rückfrage: Eine Erklärung oder Absage ohne Zahl braucht keinen Monat (#189).
          rueckfrage !== null &&
          !/monat/i.test(text) && (
            <p className="font-sans text-16 text-slate">Nennen Sie bitte auch den Monat, zum Beispiel „März 2025“.</p>
          )
        )}
        {rueckfrage === null && antwort.belege[0] && <BelegLink quelle={antwort.belege[0].quelle} sql={antwort.belege[0].sql} />}
      </div>
    );
  }

  const definition = definitionFuer(ergebnis, definitionen);
  const verstanden = verstandenSatz(antwort);
  const [beleg] = antwort.belege;
  const eine = antwort.zahlen.length === 1 ? antwort.zahlen[0] : undefined;
  const kopf = eine ? null : kopfSatz(antwort.text);
  // Vorläufig, sobald irgendein Beleg vorläufig ist; veröffentlicht nur, wenn alle Belege endgültig sind (Review !104).
  const staende = antwort.belege.map((b) => b.stand);
  const stand = staende.includes("vorlaeufig")
    ? "vorlaeufig"
    : staende.length > 0 && staende.every((st) => st === "endgueltig")
      ? "veroeffentlicht"
      : null;
  // Alle Abfragen in einem Beleg: ein Beleg je Antwort.
  const sqls = [...new Set(antwort.belege.map((b) => b.sql).filter((s): s is string => Boolean(s)))];

  return (
    <div className="flex flex-col gap-6">
      {eine ? (
        <div className="flex flex-col gap-1">
          <p className="font-display text-56 font-bold tabular-nums text-ink">{zahlText(eine.wert, eine.einheit)}</p>
          <p className="font-sans text-16 text-ink">{teileBezeichnung(eine.bezeichnung).was}</p>
        </div>
      ) : (
        <p className="font-sans text-20 font-semibold text-pretty text-ink">{kopf}</p>
      )}

      {verstanden && !(kopf && kopfSagtVerstanden(kopf)) && <p className="font-sans text-16 text-slate">{verstanden}</p>}

      {!eine && <Tabelle antwort={antwort} />}

      <div className="flex flex-wrap items-start gap-x-6 gap-y-2">
        {stand && <StandPunkt stand={stand} className="min-h-6" />}
        {beleg && (
          <BelegLink
            quelle={beleg.quelle}
            lieferung={beleg.lieferung}
            monat={beleg.monat}
            regelstand={beleg.regelstand}
            lauf={beleg.lauf}
            stand={beleg.stand}
            verweis={beleg.ref}
            sql={sqls.join("\n\n") || beleg.sql}
            text="Abfrage ansehen"
          />
        )}
      </div>

      <details className="max-w-3xl">
        <summary className="inline-flex min-h-11 cursor-pointer items-center font-sans text-14 text-slate underline decoration-line underline-offset-4 hover:text-ink">
          Details
        </summary>
        <div className="mt-2 flex flex-col gap-4">
          <p className="font-sans text-16 text-pretty text-ink">{antwort.text}</p>
          {definition && (
            <div className="flex flex-col gap-1">
              <h3 className="font-sans text-14 font-semibold text-ink">Was gezählt wird</h3>
              <p className="font-sans text-14 text-pretty text-ink">{definition}</p>
            </div>
          )}
          <div>
            <button type="button" className={textLink} onClick={() => herunterladen(antwort)}>
              Zahlen als Tabelle herunterladen
            </button>
          </div>
        </div>
      </details>
    </div>
  );
}

function Tabelle({ antwort }: { antwort: UcAntwort }) {
  const t = antwortTabelle(antwort.zahlen);
  return (
    <div className="overflow-x-auto">
      <table className="w-full max-w-3xl border-collapse">
        <caption className="sr-only">{`Zahlen zu: ${kopfSatz(antwort.text)}`}</caption>
        <thead>
          <tr className="border-b border-line">
            <th scope="col" className="py-2 pr-6 text-left">
              <span className="sr-only">Zeile</span>
            </th>
            {t.spalten.map((s) => (
              <th key={s.titel} scope="col" className="py-2 pr-6 text-right font-sans text-14 font-medium text-slate">
                {s.einheit ? `${s.titel} in ${s.einheit}` : s.titel}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {t.zeilen.map((z) => (
            <tr
              key={z.titel}
              className={`border-b border-line font-sans text-14 text-ink ${istSummenzeile(z.titel) ? "font-semibold" : ""}`}
            >
              <th scope="row" className={`py-2 pr-6 text-left ${istSummenzeile(z.titel) ? "font-semibold" : "font-normal"}`}>
                {z.titel}
              </th>
              {z.werte.map((w, i) => (
                <td key={t.spalten[i]?.titel ?? i} className="py-2 pr-6 text-right tabular-nums">
                  {w === null ? "" : formatZahl(w)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
