"use client";

import { useEffect, useState } from "react";
import { Status } from "../basis/status";
import { WarnChip } from "../bausteine/chips";
import { ModellPille } from "../bausteine/modell-pille";
import { abweichendZuletzt, modellStatusSchema, type ModellStatus } from "./modell-status";

// Modell-Badge (Pen-Frames CKCV4 und nas8Y): zeigt, welches Sprachmodell gerade antwortet, als Pille mit
// „Modell:“ und `provider · modell`. Kein Auf-/Ab-Symbol: es gibt hier keine Auswahl (Review !45).
// `lang` zeigt die lange Form wie CKCV4: „Modell: azure · gpt-5-4-mini · austauschbar“.
// Der Wert steht in Mono, weil er ein Datum ist, die Wörter in Inter. Im Mock-Betrieb steht statt „mock · mock“
// ein Satz in Alltagssprache (Abnahme #64).
// Hat laut Protokoll zuletzt ein anderer Provider oder eine Ausweichstufe geantwortet, steht das ruhig daneben,
// Symbol plus Wort, kein Alarmrot. Im Header nur „zuletzt mistral“; die Stufe hören Screenreader und steht im
// Titel, damit der Header bei 390 px nicht waagrecht überläuft.

/** Der Status wird alle 30 s und beim Zurückkehren in den Tab neu gelesen, damit „zuletzt“ nicht veraltet. */
const NEULADEN_MS = 30_000;

type Zustand = { art: "laden" } | { art: "ok"; status: ModellStatus } | { art: "fehler" };

/** Sichtbarer Satz statt „mock · mock“: auch für Bürger verständlich (Abnahme #64-5). */
export const TESTBETRIEB_TEXT = "Testbetrieb: keine KI angeschlossen";

export function ModellBadge({
  quelle = "/api/plattform/modell",
  lang = false,
  vorgabe = null,
}: {
  quelle?: string;
  lang?: boolean;
  /** Modell der aktuellen Seite (`SeitenModell`); hat Vorrang vor der globalen Einstellung. */
  vorgabe?: { provider: string; modell?: string | null; gewaehlt?: boolean } | null;
}) {
  const [zustand, setZustand] = useState<Zustand>({ art: "laden" });

  useEffect(() => {
    let abbruch = new AbortController();
    const laden = () => {
      abbruch.abort();
      abbruch = new AbortController();
      const signal = abbruch.signal;
      fetch(quelle, { signal, cache: "no-store" })
        .then(async (antwort) => {
          const geprueft = modellStatusSchema.safeParse(await antwort.json());
          if (signal.aborted) return;
          if (!antwort.ok || !geprueft.success || geprueft.data.provider === "unbekannt") {
            setZustand({ art: "fehler" });
            return;
          }
          setZustand({ art: "ok", status: geprueft.data });
        })
        .catch(() => {
          if (!signal.aborted) setZustand({ art: "fehler" });
        });
    };
    const beiSichtbar = () => {
      if (document.visibilityState === "visible") laden();
    };
    laden();
    const takt = setInterval(laden, NEULADEN_MS);
    document.addEventListener("visibilitychange", beiSichtbar);
    return () => {
      clearInterval(takt);
      document.removeEventListener("visibilitychange", beiSichtbar);
      abbruch.abort();
    };
  }, [quelle]);

  // Die Seite darf nur Testbetrieb melden oder den Anbieter bestätigen, den der Server wirklich meldet; sonst
  // zeigte der Badge einen erfundenen Anbieter (Review !66).
  // Ausnahme: Die Seite wählt den Anbieter selbst für ihre Anfragen (gewaehlt, Modellwahl auf /uc4).
  const vorgabeGilt =
    vorgabe !== null &&
    (vorgabe.provider === "mock" ||
      vorgabe.gewaehlt === true ||
      (zustand.art === "ok" && zustand.status.provider === vorgabe.provider));
  if (vorgabe && vorgabeGilt) {
    const seiteMock = vorgabe.provider === "mock";
    return (
      <ModellPille
        aria-live="polite"
        title={vorgabe.gewaehlt ? "Auf dieser Seite gewählt" : "Angabe dieser Seite"}
        data-testid="modell-badge"
        data-modell-seite=""
      >
        {seiteMock ? (
          <span data-modell-mock="">{TESTBETRIEB_TEXT}</span>
        ) : (
          <>
            <span>Modell:</span>
            <span className="font-mono">{vorgabe.modell ? `${vorgabe.provider} · ${vorgabe.modell}` : vorgabe.provider}</span>
          </>
        )}
      </ModellPille>
    );
  }

  if (zustand.art === "fehler") {
    return (
      <WarnChip data-testid="modell-badge">Modell nicht erreichbar</WarnChip>
    );
  }

  const anders = zustand.art === "ok" ? abweichendZuletzt(zustand.status) : null;
  const mock = zustand.art === "ok" && zustand.status.provider === "mock";
  const wert = zustand.art === "ok" ? `${zustand.status.provider} · ${zustand.status.modell}` : "wird geprüft";
  const titel =
    zustand.art === "ok"
      ? [zustand.status.version && `Version ${zustand.status.version}`, `Quelle: ${zustand.status.quelle}`]
          .filter(Boolean)
          .join(", ")
      : undefined;

  return (
    <ModellPille aria-live="polite" title={titel} data-testid="modell-badge">
      {mock ? (
        <span data-modell-mock="">{TESTBETRIEB_TEXT}</span>
      ) : (
        <>
          <span>Modell:</span>
          <span className={zustand.art === "ok" ? "font-mono" : undefined}>{wert}</span>
          {lang && <span>· austauschbar</span>}
        </>
      )}
      {anders && (
        <Status
          art="info"
          klein
          data-testid="modell-zuletzt"
          title={`Zuletzt hat ${anders.provider} geantwortet, Stufe ${anders.fallback_stufe}.`}
        >
          {`zuletzt ${anders.provider}`}
          <span className={lang ? undefined : "sr-only"}>{` (Stufe ${anders.fallback_stufe})`}</span>
        </Status>
      )}
    </ModellPille>
  );
}
