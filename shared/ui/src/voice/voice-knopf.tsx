"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Knopf } from "../basis/knopf";
import { klassen } from "../basis/klassen";
import { Status } from "../basis/status";
import { VOICE_KONFIGURATION_QUELLE, voiceKonfigurationSchema, type VoiceKonfiguration } from "./konfiguration";
import { istMikrofonFehler, type VoiceSdk, type VoiceSdkLader, type VoiceTranskript } from "./sdk";

// VoiceKnopf (#61, Sprach-Pegel): ein Knopf mit Mikrofon, daneben ein flacher Pegelbalken und der Zustand in
// Worten („Hört zu · 0:07“, „Denkt“, „Spricht“). Kein Glow, kein Orb, keine Animation schneller als 3 Hz; bei
// `prefers-reduced-motion` springt der Balken ohne Übergang und nur einmal je Sekunde.
// Voice ist Zusatz: Ohne Schlüssel oder Assistent bleibt der Knopf deaktiviert und sagt, dass die Frage als
// Text geht. Keine Next-Imports, das SDK kommt über `ladeSdk` herein (siehe ./sdk.ts).

export type VoiceZustand = "pruefen" | "aus" | "bereit" | "verbindet" | "hoert" | "denkt" | "spricht" | "fehler";
export type VoiceFehler = "konfiguration" | "laden" | "mikrofon" | "start" | "verbindung";

export const VOICE_AUS_TEXT = "Sprache ist hier nicht eingerichtet, die Frage geht auch als Text.";
export const VOICE_SPEICHER_HINWEIS = "Nur der Text wird gespeichert.";
const BEENDEN_HINWEIS = "Erneut klicken oder Esc beendet das Gespräch.";

export const VOICE_FEHLER_TEXT: Record<VoiceFehler, string> = {
  konfiguration: "Die Spracheinstellung ist nicht erreichbar. Die Frage geht als Text.",
  laden: "Die Sprachfunktion ließ sich nicht laden. Die Frage geht als Text.",
  mikrofon: "Kein Zugriff auf das Mikrofon. Im Browser erlauben oder als Text fragen.",
  start: "Das Gespräch ließ sich nicht starten. Erneut versuchen oder als Text fragen.",
  verbindung: "Die Verbindung ist abgebrochen. Erneut versuchen oder als Text fragen.",
};

const ZUSTAND_WORT: Record<Exclude<VoiceZustand, "fehler">, string> = {
  pruefen: "Sprache wird geprüft",
  aus: "Sprache aus",
  bereit: "Bereit",
  verbindet: "Verbindet",
  hoert: "Hört zu",
  denkt: "Denkt",
  spricht: "Spricht",
};

/** Abstand zwischen zwei Pegel-Anzeigen: 340 ms, also unter 3 Hz. Mit reduzierter Bewegung 1 s. */
export const PEGEL_TAKT_MS = 340;
const PEGEL_TAKT_RUHIG_MS = 1000;

type LaufZustand = Extract<VoiceZustand, "bereit" | "verbindet" | "hoert" | "denkt" | "spricht" | "fehler">;
const IM_GESPRAECH: ReadonlySet<VoiceZustand> = new Set(["verbindet", "hoert", "denkt", "spricht"]);
const MIT_ZEIT: ReadonlySet<VoiceZustand> = new Set(["hoert", "denkt", "spricht"]);

/** Fest gesetzter Zustand ohne SDK, für die Bausteine-Seite und Vorschauen. */
export type VoiceVorschau = { zustand: VoiceZustand; pegel?: number; sekunden?: number; fehler?: VoiceFehler };

export type VoiceKnopfProps = {
  /** Assistent dieses Raums. Fehlt er, gilt `assistantId` aus der Konfiguration. */
  assistantId?: string | null;
  /** Erhält jeden finalen Transkript-Abschnitt, nie Zwischenstände. */
  onTranskript?: (transkript: VoiceTranskript) => void;
  /** Lädt das SDK beim ersten Klick. Fehlt der Lader, bleibt der Knopf aus. */
  ladeSdk?: VoiceSdkLader;
  /** Fertige Konfiguration; sonst holt der Knopf sie selbst von `konfigurationsQuelle`. */
  konfiguration?: VoiceKonfiguration;
  konfigurationsQuelle?: string;
  vorschau?: VoiceVorschau;
  beschriftung?: string;
  className?: string;
};

type Konfig = { art: "laden" } | { art: "ok"; wert: VoiceKonfiguration } | { art: "fehler" };

function formatDauer(sekunden: number): string {
  const s = Math.max(0, Math.floor(sekunden));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function begrenze(pegel: number): number {
  return Number.isFinite(pegel) ? Math.min(1, Math.max(0, pegel)) : 0;
}

function MikrofonSymbol() {
  return (
    <svg
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className="size-4 shrink-0"
    >
      <rect x="5.5" y="1.75" width="5" height="8" rx="2.5" />
      <path d="M3.25 7.5a4.75 4.75 0 0 0 9.5 0" />
      <path d="M8 12.25v2" />
    </svg>
  );
}

function useBewegungReduziert(): boolean {
  const [reduziert, setReduziert] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const abfrage = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduziert(abfrage.matches);
    const beiWechsel = (e: MediaQueryListEvent) => setReduziert(e.matches);
    abfrage.addEventListener?.("change", beiWechsel);
    return () => abfrage.removeEventListener?.("change", beiWechsel);
  }, []);
  return reduziert;
}

export function VoiceKnopf({
  assistantId: assistantIdProp,
  onTranskript,
  ladeSdk,
  konfiguration,
  konfigurationsQuelle = VOICE_KONFIGURATION_QUELLE,
  vorschau,
  beschriftung = "Mit Stimme fragen",
  className,
}: VoiceKnopfProps) {
  const hinweisId = useId();
  const reduziert = useBewegungReduziert();

  const [konfig, setKonfig] = useState<Konfig>(() =>
    konfiguration ? { art: "ok", wert: konfiguration } : { art: "laden" },
  );
  const [lauf, setLauf] = useState<LaufZustand>("bereit");
  const [fehler, setFehler] = useState<VoiceFehler | null>(null);
  const [sekunden, setSekunden] = useState(0);
  const [pegel, setPegel] = useState(0);

  const laufRef = useRef<LaufZustand>("bereit");
  const sdkRef = useRef<VoiceSdk | null>(null);
  const sitzungRef = useRef(0);
  const startZeitRef = useRef(0);
  const pegelFernRef = useRef(0);
  const pegelNahRef = useRef<number | null>(null);
  const transkriptRef = useRef(onTranskript);
  useEffect(() => {
    transkriptRef.current = onTranskript;
  }, [onTranskript]);

  const setze = useCallback((z: LaufZustand, f: VoiceFehler | null = null) => {
    laufRef.current = z;
    setLauf(z);
    setFehler(f);
    if (!IM_GESPRAECH.has(z)) {
      pegelFernRef.current = 0;
      pegelNahRef.current = null;
      setPegel(0);
    }
  }, []);

  // Konfiguration: Prop gewinnt, sonst einmal von der Route holen (Schlüssel zur Laufzeit, nicht zur Build-Zeit).
  useEffect(() => {
    if (vorschau) return;
    if (konfiguration) {
      setKonfig({ art: "ok", wert: konfiguration });
      return;
    }
    const abbruch = new AbortController();
    fetch(konfigurationsQuelle, { signal: abbruch.signal, cache: "no-store" })
      .then(async (antwort) => {
        const geprueft = voiceKonfigurationSchema.safeParse(await antwort.json());
        if (abbruch.signal.aborted) return;
        setKonfig(antwort.ok && geprueft.success ? { art: "ok", wert: geprueft.data } : { art: "fehler" });
      })
      .catch(() => {
        if (!abbruch.signal.aborted) setKonfig({ art: "fehler" });
      });
    return () => abbruch.abort();
  }, [konfiguration, konfigurationsQuelle, vorschau]);

  const wert = konfig.art === "ok" ? konfig.wert : null;
  const assistantId = assistantIdProp || wert?.assistantId || null;
  // `aktiv` beschreibt den Standard-Assistenten der Route. Ein Raum mit eigenem Assistenten braucht nur den
  // öffentlichen Schlüssel; scheitert der Custom-LLM-Weg, zeigt der Knopf den Fehler und der Text bleibt.
  const eingerichtet = Boolean(
    ladeSdk && wert?.publicKey && assistantId && (wert.aktiv || Boolean(assistantIdProp)),
  );

  const beenden = useCallback(() => {
    sitzungRef.current += 1;
    setze("bereit");
    const sdk = sdkRef.current;
    if (!sdk) return;
    try {
      Promise.resolve(sdk.stop()).catch(() => undefined);
    } catch {
      // Beenden darf nie selbst einen Fehler zeigen.
    }
  }, [setze]);

  const verbinde = useCallback(
    (sdk: VoiceSdk) => {
      sdk.on("call-start", () => {
        if (laufRef.current !== "verbindet") return;
        startZeitRef.current = Date.now();
        setSekunden(0);
        setze("hoert");
      });
      sdk.on("call-end", () => {
        if (laufRef.current !== "fehler") setze("bereit");
      });
      sdk.on("speech-start", () => {
        if (MIT_ZEIT.has(laufRef.current)) setze("spricht");
      });
      sdk.on("speech-end", () => {
        if (laufRef.current === "spricht") setze("hoert");
      });
      sdk.on("volume-level", (p) => {
        pegelFernRef.current = begrenze(p);
      });
      sdk.on("local-volume-level", (p) => {
        pegelNahRef.current = begrenze(p);
      });
      sdk.on("message", (nachricht) => {
        if (nachricht?.type !== "transcript" || nachricht.transcriptType !== "final") return;
        const text = (nachricht.transcript ?? "").trim();
        if (!text) return;
        const rolle = nachricht.role === "assistant" ? "assistent" : "nutzer";
        transkriptRef.current?.({ rolle, text });
        if (rolle === "nutzer" && laufRef.current === "hoert") setze("denkt");
      });
      sdk.on("error", (e) => {
        if (!IM_GESPRAECH.has(laufRef.current)) return;
        const art: VoiceFehler = istMikrofonFehler(e)
          ? "mikrofon"
          : laufRef.current === "verbindet"
            ? "start"
            : "verbindung";
        sitzungRef.current += 1;
        setze("fehler", art);
        try {
          Promise.resolve(sdk.stop()).catch(() => undefined);
        } catch {
          // ignoriert
        }
      });
    },
    [setze],
  );

  const starten = useCallback(async () => {
    if (!ladeSdk || !wert?.publicKey || !assistantId) return;
    const sitzung = ++sitzungRef.current;
    setSekunden(0);
    setze("verbindet");
    let sdk = sdkRef.current;
    if (!sdk) {
      try {
        sdk = await ladeSdk(wert.publicKey);
      } catch {
        if (sitzung === sitzungRef.current) setze("fehler", "laden");
        return;
      }
      sdkRef.current = sdk;
      verbinde(sdk);
    }
    if (sitzung !== sitzungRef.current) return;
    try {
      const anruf = await sdk.start(assistantId);
      if (sitzung === sitzungRef.current && anruf === null && laufRef.current === "verbindet") {
        setze("fehler", "start");
      }
    } catch (e) {
      if (sitzung === sitzungRef.current) setze("fehler", istMikrofonFehler(e) ? "mikrofon" : "start");
    }
  }, [assistantId, ladeSdk, setze, verbinde, wert?.publicKey]);

  // Sekundenzähler, 1 Hz.
  useEffect(() => {
    if (!MIT_ZEIT.has(lauf)) return;
    const takt = setInterval(() => setSekunden((Date.now() - startZeitRef.current) / 1000), 1000);
    return () => clearInterval(takt);
  }, [lauf]);

  // Pegel höchstens alle 340 ms übernehmen (unter 3 Hz). Beim Zuhören zählt das Mikrofon, sonst die Stimme.
  useEffect(() => {
    if (!MIT_ZEIT.has(lauf)) return;
    const takt = setInterval(
      () => {
        const nah = pegelNahRef.current;
        const neu = lauf === "hoert" && nah !== null ? nah : pegelFernRef.current;
        setPegel(Math.round(neu * 20) / 20);
      },
      reduziert ? PEGEL_TAKT_RUHIG_MS : PEGEL_TAKT_MS,
    );
    return () => clearInterval(takt);
  }, [lauf, reduziert]);

  // Escape beendet ein laufendes Gespräch, egal wo der Fokus steht.
  useEffect(() => {
    if (vorschau || !IM_GESPRAECH.has(lauf)) return;
    const beiTaste = (e: KeyboardEvent) => {
      if (e.key === "Escape") beenden();
    };
    document.addEventListener("keydown", beiTaste);
    return () => document.removeEventListener("keydown", beiTaste);
  }, [beenden, lauf, vorschau]);

  // Beim Verlassen der Seite das Gespräch schließen.
  useEffect(
    () => () => {
      sitzungRef.current += 1;
      const sdk = sdkRef.current;
      if (!sdk) return;
      try {
        Promise.resolve(sdk.stop()).catch(() => undefined);
        sdk.removeAllListeners?.();
      } catch {
        // ignoriert
      }
    },
    [],
  );

  // Angezeigter Zustand.
  let zustand: VoiceZustand;
  let fehlerArt: VoiceFehler | null = null;
  let anzeigePegel = pegel;
  let anzeigeSekunden = sekunden;
  if (vorschau) {
    zustand = vorschau.zustand;
    fehlerArt = vorschau.zustand === "fehler" ? (vorschau.fehler ?? "verbindung") : null;
    anzeigePegel = begrenze(vorschau.pegel ?? 0);
    anzeigeSekunden = vorschau.sekunden ?? 0;
  } else if (konfig.art === "laden") {
    zustand = "pruefen";
  } else if (konfig.art === "fehler") {
    zustand = "fehler";
    fehlerArt = "konfiguration";
  } else if (!eingerichtet) {
    zustand = "aus";
  } else {
    zustand = lauf;
    fehlerArt = fehler;
  }

  const imGespraech = IM_GESPRAECH.has(zustand);
  const gesperrt = zustand === "aus" || zustand === "pruefen" || fehlerArt === "konfiguration";
  const balken = !gesperrt;
  const hinweis =
    zustand === "aus"
      ? VOICE_AUS_TEXT
      : imGespraech
        ? `${VOICE_SPEICHER_HINWEIS} ${BEENDEN_HINWEIS}`
        : VOICE_SPEICHER_HINWEIS;

  const beiKlick = () => {
    if (vorschau || gesperrt) return;
    if (imGespraech) beenden();
    else void starten();
  };

  return (
    <div className={klassen("flex flex-col gap-2", className)} data-voice-zustand={zustand}>
      <div className="flex flex-wrap items-center gap-4">
        <Knopf
          art={imGespraech ? "primaer" : "sekundaer"}
          aria-pressed={imGespraech}
          aria-describedby={hinweisId}
          disabled={gesperrt}
          onClick={beiKlick}
          className="min-h-11"
        >
          <MikrofonSymbol />
          {beschriftung}
        </Knopf>
        {balken && (
          <div
            className="h-2 w-32 shrink-0 overflow-hidden rounded-sm bg-line"
            aria-hidden="true"
            data-testid="voice-pegel"
          >
            <div
              className="h-full bg-gruen transition-[width] duration-300 ease-out motion-reduce:transition-none"
              style={{ width: `${Math.round(anzeigePegel * 100)}%` }}
            />
          </div>
        )}
        <p role="status" aria-live="polite" className="font-sans text-14 text-ink" data-testid="voice-zustand">
          {zustand === "fehler" && fehlerArt ? (
            <Status art="fehler">{VOICE_FEHLER_TEXT[fehlerArt]}</Status>
          ) : (
            <>
              {ZUSTAND_WORT[zustand as Exclude<VoiceZustand, "fehler">]}
              {zustand === "hoert" && (
                <span aria-hidden="true">
                  {" · "}
                  <span className="font-mono tabular-nums">{formatDauer(anzeigeSekunden)}</span>
                </span>
              )}
            </>
          )}
        </p>
      </div>
      <p id={hinweisId} className="font-sans text-12 text-slate">
        {hinweis}
      </p>
    </div>
  );
}
