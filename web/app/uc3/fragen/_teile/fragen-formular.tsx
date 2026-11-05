"use client";

import { useRef, useState, type FormEvent } from "react";
import type { UcAntwort } from "@kic/ui/antwortform";
import { Feld, Fliesstext, Knopf, Status, Tabelle, Zahl } from "@kic/ui/basis";
import { HerkunftChip } from "@kic/ui/bausteine";
import { alsCsv, istRueckfrage } from "@/components/uc3/antwort";
import { istMonat, monatName } from "@/components/uc3/monat";

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

const BEISPIELE = [
  "Beschäftigte in Wien im März 2025",
  "Beschäftigte im Oktober 2025 je Bundesland",
  "Beschäftigte 2025",
] as const;

/** Ab so vielen Zahlen je Abfrage zeigt die Seite ab 768 px eine Tabelle statt einer Liste. */
const TABELLE_AB = 4;

const FEHLERSATZ: Record<number, string> = {
  403: "Fragen an die Daten sind in der Online-Demo gesperrt.",
  415: "Die Seite hat die Frage in einer falschen Form geschickt. Bitte die Seite neu laden.",
  413: "Die Frage ist zu lang. Bitte kürzer fragen.",
  429: "Gerade rechnet das Programm schon zwei Fragen. Bitte gleich noch einmal fragen.",
  502: "Das Programm konnte die Frage gerade nicht beantworten. Bitte gleich noch einmal fragen.",
};

const textKnopf =
  "inline-flex min-h-11 items-center font-sans text-14 font-semibold text-gruen underline underline-offset-4 hover:no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen";

function lieferungText(lieferung: string | null | undefined): string | null {
  if (!lieferung) return null;
  return istMonat(lieferung) ? monatName(lieferung) : lieferung;
}

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

/** Satz für die Online-Demo, in der nichts gerechnet und nichts geändert wird (KIC_ONLINE_LESEND=1). */
const NUR_ANSEHEN = "Online nur zum Ansehen: Fragen an die Daten stellen Sie in der lokalen Anwendung.";

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

  async function senden(text: string) {
    const sauber = text.trim();
    if (!sauber) {
      setEingabeFehler("Bitte eine Frage eingeben.");
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
      setZustand({ art: "fehler", satz: "Die Seite hat keine Verbindung zum Programm. Bitte gleich noch einmal fragen." });
    }
  }

  function absenden(ereignis: FormEvent<HTMLFormElement>) {
    ereignis.preventDefault();
    void senden(frage);
  }

  return (
    <div className="flex max-w-4xl flex-col gap-8">
      {nurLesen && (
        <Fliesstext groesse={14} ton="gedaempft">
          {NUR_ANSEHEN}
        </Fliesstext>
      )}
      <form onSubmit={absenden} className="flex flex-col gap-4" aria-label="Frage an die Daten">
        <div className="flex flex-col gap-4 md:flex-row md:items-end">
          <Feld
            label="Ihre Frage"
            name="frage"
            value={frage}
            maxLength={500}
            autoComplete="off"
            placeholder="z. B. Beschäftigte in Wien im März 2025"
            hinweis="Nennen Sie einen Monat. Enter sendet die Frage."
            fehler={eingabeFehler}
            onChange={(e) => setFrage(e.target.value)}
            disabled={nurLesen}
            className="min-w-0 flex-1"
          />
          <Knopf type="submit" className="min-h-11 md:mb-6" disabled={nurLesen || zustand.art === "laedt"}>
            Fragen
          </Knopf>
        </div>
        <div className="flex flex-col gap-2">
          <p className="font-sans text-14 text-slate" id="beispiele-titel">
            Beispiele zum Ausprobieren:
          </p>
          <ul className="flex flex-wrap gap-2" aria-labelledby="beispiele-titel">
            {BEISPIELE.map((beispiel) => (
              <li key={beispiel}>
                <button
                  type="button"
                  disabled={nurLesen}
                  onClick={() => {
                    setFrage(beispiel);
                    void senden(beispiel);
                  }}
                  className="min-h-11 rounded-full border border-line bg-white px-4 py-2 text-left font-sans text-14 text-ink hover:border-gruen hover:text-gruen disabled:cursor-not-allowed disabled:text-slate disabled:hover:border-line focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen"
                >
                  {beispiel}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </form>

      <section aria-labelledby="ergebnis-titel" className="flex flex-col gap-4">
        <h2 id="ergebnis-titel" className="sr-only">
          Antwort des Programms
        </h2>
        <div aria-live="polite" aria-busy={zustand.art === "laedt"} className="flex flex-col gap-4">
          {zustand.art === "laedt" && <Fliesstext ton="gedaempft">Das Programm rechnet …</Fliesstext>}
          {zustand.art === "fehler" && <Status art="fehler">{zustand.satz}</Status>}
          {zustand.art === "fertig" && <Antwort ergebnis={zustand.ergebnis} definitionen={definitionen} />}
        </div>
      </section>
    </div>
  );
}

function Antwort({ ergebnis, definitionen }: { ergebnis: Ergebnis; definitionen: readonly Definition[] }) {
  const { antwort, rueckfrage } = ergebnis;

  if (istRueckfrage(antwort, rueckfrage)) {
    const text = rueckfrage ?? antwort.text;
    return (
      <div className="flex flex-col gap-2 border-l-2 border-navy pl-4">
        <Status art="info">Rückfrage</Status>
        <Fliesstext>{text}</Fliesstext>
        {!/monat/i.test(text) && (
          <Fliesstext groesse={14} ton="gedaempft">
            Nennen Sie bitte auch den Monat, zum Beispiel „März 2025“.
          </Fliesstext>
        )}
      </div>
    );
  }

  const definition = definitionFuer(ergebnis, definitionen);
  const sqls = [...new Set(antwort.belege.map((b) => b.sql).filter((s): s is string => Boolean(s)))];
  // Zahlen nach Beleg gruppiert: eine Abfrage liefert oft alle Zahlen einer Gruppe (z. B. je Bundesland).
  const gruppen = antwort.belege
    .map((beleg, index) => ({ beleg, zahlen: antwort.zahlen.filter((z) => z.beleg === index) }))
    .filter((g) => g.zahlen.length > 0);

  return (
    <div className="flex flex-col gap-6">
      <p className="font-sans text-20 font-semibold text-pretty text-ink">{antwort.text}</p>

      {gruppen.map(({ beleg, zahlen }, gruppe) => {
        const lieferung = lieferungText(beleg.lieferung ?? beleg.monat);
        return (
          <div key={gruppe} className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              {beleg.stand === "endgueltig" ? (
                <Status art="ok">endgültig</Status>
              ) : beleg.stand === "vorlaeufig" ? (
                <Status art="info">vorläufig</Status>
              ) : null}
              {lieferung && <Fliesstext groesse={14} ton="gedaempft">{`Lieferung ${lieferung}`}</Fliesstext>}
            </div>

            <ul
              className={zahlen.length >= TABELLE_AB ? "flex flex-col md:hidden" : "flex flex-col"}
              aria-label={zahlen.length >= TABELLE_AB ? "Zahlen als Liste" : "Zahlen"}
            >
              {zahlen.map((z) => (
                <li
                  key={z.bezeichnung}
                  className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-line py-2"
                >
                  <span className="min-w-0 font-sans text-14 text-ink">{z.bezeichnung}</span>
                  <span className="flex items-baseline gap-2">
                    <Zahl wert={z.wert} className={zahlen.length === 1 ? "text-32 font-bold text-ink" : "text-16 text-ink"} />
                    {z.einheit && <span className="font-sans text-12 text-slate">{z.einheit}</span>}
                  </span>
                </li>
              ))}
            </ul>
            {zahlen.length >= TABELLE_AB && (
              <Tabelle
                className="hidden md:table"
                beschriftung={`Zahlen zu: ${antwort.text}`}
                spalten={[
                  { schluessel: "bezeichnung", titel: "Bezeichnung" },
                  { schluessel: "wert", titel: "Wert", zahl: true },
                  { schluessel: "einheit", titel: "Einheit" },
                ]}
                zeilen={zahlen.map((z) => ({
                  bezeichnung: z.bezeichnung,
                  wert: <Zahl wert={z.wert} />,
                  einheit: z.einheit ?? "",
                }))}
                zeilenSchluessel={(_, i) => zahlen[i]?.bezeichnung ?? String(i)}
              />
            )}

            <div className="flex flex-col gap-1">
              <Fliesstext groesse={12} ton="gedaempft">
                {zahlen.length === 1 ? "Herkunft dieser Zahl:" : `Herkunft dieser ${zahlen.length} Zahlen (eine Abfrage):`}
              </Fliesstext>
              <HerkunftChip
                quelle={beleg.quelle}
                lieferung={beleg.lieferung}
                monat={beleg.monat}
                regelstand={beleg.regelstand}
                lauf={beleg.lauf}
                stand={beleg.stand}
                sql={beleg.sql}
                verweis={beleg.ref}
              />
            </div>
          </div>
        );
      })}

      <div>
        <button type="button" className={textKnopf} onClick={() => herunterladen(antwort)}>
          Als Tabelle herunterladen
        </button>
      </div>

      {(sqls.length > 0 || definition) && (
        <details className="group border-t border-line pt-4">
          <summary className="min-h-11 cursor-pointer font-sans text-16 font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen">
            So haben wir gerechnet
          </summary>
          <div className="flex flex-col gap-4 pt-2">
            {definition && (
              <div className="flex flex-col gap-1">
                <p className="font-sans text-14 font-semibold text-ink">Was gezählt wird</p>
                <Fliesstext groesse={14}>{definition}</Fliesstext>
              </div>
            )}
            {sqls.map((sql, i) => (
              <div key={sql} className="flex flex-col gap-1">
                <p className="font-sans text-14 font-semibold text-ink">
                  {sqls.length === 1 ? "Die Abfrage" : `Abfrage ${i + 1}`}
                </p>
                <pre className="max-w-full overflow-x-auto whitespace-pre-wrap break-words border-l-2 border-line pl-4 font-mono text-12 text-ink">
                  <code>{sql}</code>
                </pre>
              </div>
            ))}
          </div>
        </details>
      )}

      <Fliesstext groesse={12} ton="gedaempft">
        Ohne KI gerechnet: Die Zahl kommt aus der Datenbank, die Abfrage steht oben.
      </Fliesstext>
    </div>
  );
}
