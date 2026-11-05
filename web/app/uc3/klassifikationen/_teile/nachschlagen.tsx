"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { Art, Auswahl, Kinder, Knoten, Treffer } from "@/components/uc3/klassifikation-tief";

// Nachschlagen (#189): ein Suchfeld und aufklappbare Ebenen, ÖNACE je Fassung und Regionen je Stand. Die Kinder kommen
// erst beim Aufklappen, die Liste wäre sonst Zehntausende Zeilen lang. Nur lesend, ohne Zahlen: Die Statistik zählt nach
// Abschnitt und Bundesland, nicht tiefer.

const ADRESSE = "/api/uc3/klassifikationen";
const ART_WORT: Record<Art, string> = { oenace: "Branchen", region: "Regionen" };
const FEHLER = "Die Liste ist gerade nicht erreichbar.";
const STATUS = "font-sans text-14 text-slate";

function grossAnfang(satz: string): string {
  return satz.charAt(0).toUpperCase() + satz.slice(1);
}

async function hole<T>(parameter: Record<string, string>, signal?: AbortSignal): Promise<T> {
  const antwort = await fetch(`${ADRESSE}?${new URLSearchParams(parameter)}`, { signal });
  if (!antwort.ok) throw new Error(String(antwort.status));
  return (await antwort.json()) as T;
}

function NochEinmal({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="inline-flex min-h-11 items-center font-sans text-14 text-ink underline underline-offset-4 hover:text-gruen">
      Noch einmal versuchen
    </button>
  );
}

function Inhalt({ knoten, offen, klappbar }: { knoten: Knoten; offen: boolean; klappbar: boolean }) {
  return (
    <>
      <span className="w-20 shrink-0 font-sans text-14 tabular-nums text-slate">{knoten.code}</span>
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="font-sans text-16 text-ink">{knoten.name}</span>
        {knoten.pfad && <span className="font-sans text-14 text-slate">{knoten.pfad}</span>}
        {knoten.aenderungen.map((satz) => (
          <span key={satz} className="font-sans text-14 text-slate">
            {satz}
          </span>
        ))}
      </span>
      {klappbar && (
        <span aria-hidden="true" className={`shrink-0 text-slate transition-transform motion-reduce:transition-none ${offen ? "rotate-90" : ""}`}>
          ›
        </span>
      )}
    </>
  );
}

function Zeile({ knoten, art, fassung }: { knoten: Knoten; art: Art; fassung: string }) {
  const [offen, setOffen] = useState(false);
  const [kinder, setKinder] = useState<Kinder | null>(null);
  const [fehler, setFehler] = useState(false);
  const listeId = useId();

  async function laden() {
    setFehler(false);
    try {
      setKinder(await hole<Kinder>({ art, fassung, unter: knoten.code }));
    } catch {
      setFehler(true);
    }
  }

  function umschalten() {
    const neu = !offen;
    setOffen(neu);
    if (neu && !kinder) void laden();
  }

  if (!knoten.hatKinder) {
    return (
      <li className="flex items-baseline gap-3 border-b border-line py-3">
        <Inhalt knoten={knoten} offen={false} klappbar={false} />
      </li>
    );
  }
  return (
    <li className="border-b border-line last:border-b-0">
      <button
        type="button"
        aria-expanded={offen}
        aria-controls={offen ? listeId : undefined}
        onClick={umschalten}
        className="flex min-h-11 w-full items-baseline gap-3 py-3 text-left hover:bg-paper"
      >
        <Inhalt knoten={knoten} offen={offen} klappbar />
      </button>
      {offen && (
        <div id={listeId} className="pb-2 pl-3 sm:pl-5">
          {fehler && (
            <div className="flex flex-wrap items-center gap-x-3 py-1">
              <p role="status" className={STATUS}>
                {FEHLER}
              </p>
              <NochEinmal onClick={() => void laden()} />
            </div>
          )}
          {!fehler && !kinder && (
            <p role="status" className={`py-2 ${STATUS}`}>
              Wird geladen.
            </p>
          )}
          {kinder && (
            <>
              <p className="pb-1 font-sans text-14 text-slate">{kinder.ueberschrift}</p>
              <ul className="flex flex-col border-t border-line">
                {kinder.knoten.map((k) => (
                  <Zeile key={k.code} knoten={k} art={art} fassung={fassung} />
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </li>
  );
}

function Liste({ knoten, art, fassung }: { knoten: readonly Knoten[]; art: Art; fassung: string }) {
  return (
    <ul className="flex flex-col border-y border-line">
      {knoten.map((k) => (
        <Zeile key={k.code} knoten={k} art={art} fassung={fassung} />
      ))}
    </ul>
  );
}

/** Die oberste Ebene ist zu Beginn zu: Die Abschnitte stehen schon oben in der Tabelle, und die Seite bleibt kurz. */
function Oberste({ daten, art, fassung }: { daten: Kinder; art: Art; fassung: string }) {
  const [offen, setOffen] = useState(false);
  const listeId = useId();
  return (
    <div className="flex flex-col">
      <button
        type="button"
        aria-expanded={offen}
        aria-controls={offen ? listeId : undefined}
        onClick={() => setOffen(!offen)}
        className="flex min-h-11 w-full items-baseline justify-between gap-3 py-2 text-left font-sans text-16 text-ink underline-offset-4 hover:underline"
      >
        {offen ? `Alle ${daten.ueberschrift}` : `Alle ${daten.ueberschrift} aufklappen`}
        <span aria-hidden="true" className={`shrink-0 text-slate transition-transform motion-reduce:transition-none ${offen ? "rotate-90" : ""}`}>
          ›
        </span>
      </button>
      {offen && (
        <div id={listeId}>
          <Liste knoten={daten.knoten} art={art} fassung={fassung} />
        </div>
      )}
    </div>
  );
}

type Stand<T> = { zustand: "laedt" } | { zustand: "fehler" } | { zustand: "da"; daten: T };

export function Nachschlagen({ auswahl, start, startArt }: { auswahl: Auswahl; start: Kinder; startArt: Art }) {
  const [art, setArt] = useState<Art>(startArt);
  const [fassungen, setFassungen] = useState<Record<Art, string>>({
    oenace: auswahl.oenace[0]?.wert ?? "",
    region: auswahl.region[0]?.wert ?? "",
  });
  const fassung = fassungen[art];
  const [wurzel, setWurzel] = useState<Stand<Kinder>>({ zustand: "da", daten: start });
  const [suche, setSuche] = useState("");
  // Der Schlüssel sagt, wofür der Stand gilt: Alte Treffer erscheinen nie unter einer neuen Eingabe oder Auswahl.
  const [treffer, setTreffer] = useState<{ fuer: string; stand: Stand<Treffer> } | null>(null);
  const [versuch, setVersuch] = useState(0);
  const ersterLauf = useRef(true);
  const suchId = useId();
  const wahlId = useId();
  const text = suche.trim();

  useEffect(() => {
    if (ersterLauf.current) {
      ersterLauf.current = false;
      return;
    }
    const abbruch = new AbortController();
    setWurzel({ zustand: "laedt" });
    hole<Kinder>({ art, fassung }, abbruch.signal)
      .then((daten) => setWurzel({ zustand: "da", daten }))
      .catch(() => {
        if (!abbruch.signal.aborted) setWurzel({ zustand: "fehler" });
      });
    return () => abbruch.abort();
  }, [art, fassung, versuch]);

  const schluessel = `${art}|${fassung}|${text}`;
  useEffect(() => {
    if (!text) {
      setTreffer(null);
      return;
    }
    const abbruch = new AbortController();
    const zeitgeber = setTimeout(() => {
      hole<Treffer>({ art, fassung, suche: text }, abbruch.signal)
        .then((daten) => setTreffer({ fuer: schluessel, stand: { zustand: "da", daten } }))
        .catch(() => {
          if (!abbruch.signal.aborted) setTreffer({ fuer: schluessel, stand: { zustand: "fehler" } });
        });
    }, 250);
    return () => {
      clearTimeout(zeitgeber);
      abbruch.abort();
    };
  }, [art, fassung, text, schluessel, versuch]);

  const wahlen = auswahl[art];
  const arten = (Object.keys(ART_WORT) as Art[]).filter((a) => auswahl[a].length > 0);
  const ort = wahlen.find((w) => w.wert === fassung)?.ort ?? "";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        {arten.length > 1 && (
          <div role="group" aria-label="Was nachschlagen" className="flex self-start overflow-hidden rounded-md border border-line">
            {arten.map((a) => (
              <button
                key={a}
                type="button"
                aria-pressed={a === art}
                onClick={() => setArt(a)}
                className={`inline-flex min-h-11 items-center px-3 font-sans text-14 ${a === art ? "bg-ink text-white" : "text-ink hover:bg-paper"}`}
              >
                {ART_WORT[a]}
              </button>
            ))}
          </div>
        )}
        {wahlen.length > 1 && (
          <div className="flex flex-col gap-1">
            <label htmlFor={wahlId} className="sr-only">
              {art === "oenace" ? "Fassung" : "Stand"}
            </label>
            <select
              id={wahlId}
              value={fassung}
              onChange={(e) => setFassungen((f) => ({ ...f, [art]: e.target.value }))}
              className="min-h-11 rounded-md border border-line bg-white px-3 font-sans text-14 text-ink"
            >
              {wahlen.map((w) => (
                <option key={w.wert} value={w.wert}>
                  {w.name}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="flex min-w-0 flex-1 flex-col gap-1 sm:min-w-64">
          <label htmlFor={suchId} className="sr-only">
            Suche nach Code oder Name
          </label>
          <input
            id={suchId}
            type="search"
            value={suche}
            maxLength={60}
            onChange={(e) => setSuche(e.target.value)}
            placeholder={art === "oenace" ? "Zum Beispiel 10.11 oder Fleisch" : "Zum Beispiel 70101 oder Innsbruck"}
            className="min-h-11 w-full rounded-md border border-line bg-white px-3 font-sans text-16 text-ink placeholder:text-slate"
          />
        </div>
      </div>

      <Unten
        suche={text ? (treffer?.fuer === schluessel ? treffer.stand : { zustand: "laedt" }) : null}
        wurzel={wurzel}
        text={text}
        ort={ort}
        art={art}
        fassung={fassung}
        nochEinmal={() => setVersuch((v) => v + 1)}
      />
    </div>
  );
}

/** Nur die Statuszeile meldet sich beim Screenreader, nicht jede Zeile der Liste beim Aufklappen. */
function Unten({
  suche,
  wurzel,
  text,
  ort,
  art,
  fassung,
  nochEinmal,
}: {
  suche: Stand<Treffer> | null;
  wurzel: Stand<Kinder>;
  text: string;
  ort: string;
  art: Art;
  fassung: string;
  nochEinmal: () => void;
}) {
  const stand = suche ?? wurzel;
  const fehler = stand.zustand === "fehler";
  let status = "";
  let leer = false;
  if (stand.zustand === "laedt") status = suche ? "Wird gesucht." : "Wird geladen.";
  else if (fehler) status = FEHLER;
  else if (suche?.zustand === "da") {
    const { knoten, gesamt } = suche.daten;
    leer = gesamt === 0;
    status = leer
      ? `${grossAnfang(ort)} passt nichts zu „${text}“.`
      : gesamt > knoten.length
        ? `Die ersten ${knoten.length} von ${gesamt} Treffern ${ort}. Genauer suchen zeigt den Rest.`
        : `${gesamt} Treffer ${ort}.`;
  }
  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap items-center gap-x-3">
        <p aria-live="polite" className={status ? (leer ? "py-2 font-sans text-16 text-ink" : `py-1 ${STATUS}`) : "sr-only"}>
          {status}
        </p>
        {fehler && <NochEinmal onClick={nochEinmal} />}
      </div>
      {suche?.zustand === "da" && !leer && <Liste key={`${art}-${fassung}-${text}`} knoten={suche.daten.knoten} art={art} fassung={fassung} />}
      {!suche && wurzel.zustand === "da" && <Oberste key={`${art}-${fassung}`} daten={wurzel.daten} art={art} fassung={fassung} />}
    </div>
  );
}
