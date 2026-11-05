"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { Art, Auswahl, Kinder, Knoten, Treffer } from "@/components/uc3/klassifikation-tief";

// Nachschlagen (#189): ein Suchfeld und aufklappbare Ebenen, ÖNACE je Fassung und Regionen je Stand. Die Kinder kommen
// erst beim Aufklappen, die Liste wäre sonst Zehntausende Zeilen lang. Nur lesend, ohne Zahlen: Die Statistik zählt nach
// Abschnitt und Bundesland, nicht tiefer.

const ADRESSE = "/api/uc3/klassifikationen";
const ART_WORT: Record<Art, string> = { oenace: "Branchen", region: "Regionen" };
const FEHLER = "Die Liste ist gerade nicht erreichbar. Bitte noch einmal versuchen.";

async function hole<T>(parameter: Record<string, string>, signal?: AbortSignal): Promise<T> {
  const antwort = await fetch(`${ADRESSE}?${new URLSearchParams(parameter)}`, { signal });
  if (!antwort.ok) throw new Error(String(antwort.status));
  return (await antwort.json()) as T;
}

function Inhalt({ knoten, offen, klappbar }: { knoten: Knoten; offen: boolean; klappbar: boolean }) {
  return (
    <>
      <span className="w-20 shrink-0 font-sans text-14 tabular-nums text-slate">{knoten.code}</span>
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="font-sans text-16 text-ink">{knoten.name}</span>
        {knoten.pfad && <span className="font-sans text-14 text-slate">{`${knoten.ebene} in ${knoten.pfad}`}</span>}
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

  async function umschalten() {
    const neu = !offen;
    setOffen(neu);
    if (!neu || kinder) return;
    setFehler(false);
    try {
      setKinder(await hole<Kinder>({ art, fassung, unter: knoten.code }));
    } catch {
      setFehler(true);
    }
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
          {fehler && <p className="py-2 font-sans text-14 text-slate">{FEHLER}</p>}
          {!fehler && !kinder && <p className="py-2 font-sans text-14 text-slate">Wird geladen.</p>}
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
  const [treffer, setTreffer] = useState<Stand<Treffer> | null>(null);
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
  }, [art, fassung]);

  useEffect(() => {
    if (!text) {
      setTreffer(null);
      return;
    }
    const abbruch = new AbortController();
    setTreffer((vorher) => vorher ?? { zustand: "laedt" });
    const zeitgeber = setTimeout(() => {
      hole<Treffer>({ art, fassung, suche: text }, abbruch.signal)
        .then((daten) => setTreffer({ zustand: "da", daten }))
        .catch(() => {
          if (!abbruch.signal.aborted) setTreffer({ zustand: "fehler" });
        });
    }, 250);
    return () => {
      clearTimeout(zeitgeber);
      abbruch.abort();
    };
  }, [art, fassung, text]);

  const wahlen = auswahl[art];
  const arten = (Object.keys(ART_WORT) as Art[]).filter((a) => auswahl[a].length > 0);
  const fassungName = wahlen.find((w) => w.wert === fassung)?.name ?? "";

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
            placeholder={art === "oenace" ? "Code oder Name, zum Beispiel 10.11 oder Bäckerei" : "Code oder Name, zum Beispiel 70101 oder Innsbruck"}
            className="min-h-11 w-full rounded-md border border-line bg-white px-3 font-sans text-16 text-ink placeholder:text-slate"
          />
        </div>
      </div>

      <div aria-live="polite">
        {treffer ? (
          <Ergebnis stand={treffer} text={text} fassungName={fassungName} art={art} fassung={fassung} />
        ) : wurzel.zustand === "laedt" ? (
          <p className="py-2 font-sans text-14 text-slate">Wird geladen.</p>
        ) : wurzel.zustand === "fehler" ? (
          <p className="py-2 font-sans text-14 text-slate">{FEHLER}</p>
        ) : (
          <Liste key={`${art}-${fassung}`} knoten={wurzel.daten.knoten} art={art} fassung={fassung} />
        )}
      </div>
    </div>
  );
}

function Ergebnis({
  stand,
  text,
  fassungName,
  art,
  fassung,
}: {
  stand: Stand<Treffer>;
  text: string;
  fassungName: string;
  art: Art;
  fassung: string;
}) {
  if (stand.zustand === "laedt") return <p className="py-2 font-sans text-14 text-slate">Wird gesucht.</p>;
  if (stand.zustand === "fehler") return <p className="py-2 font-sans text-14 text-slate">{FEHLER}</p>;
  const { knoten, gesamt } = stand.daten;
  if (gesamt === 0) {
    return <p className="py-2 font-sans text-16 text-ink">{`In ${fassungName} passt nichts zu „${text}“.`}</p>;
  }
  const zaehlung =
    gesamt > knoten.length
      ? `Die ersten ${knoten.length} von ${gesamt} Treffern in ${fassungName}. Genauer suchen zeigt den Rest.`
      : `${gesamt} ${gesamt === 1 ? "Treffer" : "Treffer"} in ${fassungName}.`;
  return (
    <>
      <p className="pb-1 font-sans text-14 text-slate">{zaehlung}</p>
      <Liste key={`${art}-${fassung}-${text}`} knoten={knoten} art={art} fassung={fassung} />
    </>
  );
}
