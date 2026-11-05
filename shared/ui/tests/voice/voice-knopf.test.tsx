import { act, fireEvent, render, screen } from "@testing-library/react";
import {
  PEGEL_FLACH_PX,
  PEGEL_GRUNDFORM,
  PEGEL_TAKT_MS,
  pegelHoehen,
  VOICE_AUS_TEXT,
  VOICE_FEHLER_TEXT,
  VOICE_SPEICHER_HINWEIS,
  VoiceKnopf,
  type VoiceKnopfProps,
  type VoiceKonfiguration,
  type VoiceSdk,
} from "../../src/voice";

// Fängt ab: Voice wird zum einzigen Weg (Knopf ohne Schlüssel bedienbar), Zwischenstände landen als Frage im
// Raum, ein laufendes Gespräch lässt sich nicht beenden, und Fehler bleiben stumm. Kein echtes SDK, kein
// Mikrofon: das SDK ist ein Objekt, das Ereignisse auf Zuruf auslöst.

type Handler = (...args: never[]) => void;

class FalschesSdk implements VoiceSdk {
  handler = new Map<string, Handler[]>();
  start = vi.fn(async (_assistantId: string): Promise<unknown> => ({ id: "anruf-1" }));
  stop = vi.fn(async () => undefined);
  removeAllListeners = vi.fn();
  on(ereignis: string, f: Handler) {
    this.handler.set(ereignis, [...(this.handler.get(ereignis) ?? []), f]);
    return this;
  }
  emit(ereignis: string, ...args: unknown[]) {
    act(() => {
      for (const f of this.handler.get(ereignis) ?? []) (f as (...a: unknown[]) => void)(...args);
    });
  }
}

const aktiv: VoiceKonfiguration = { publicKey: "pk-test", assistantId: "asst-test", aktiv: true };

function zeige(props: Partial<VoiceKnopfProps> = {}) {
  const sdk = new FalschesSdk();
  const ladeSdk = vi.fn(async (_k: string) => sdk);
  const onTranskript = vi.fn();
  const ansicht = render(<VoiceKnopf konfiguration={aktiv} ladeSdk={ladeSdk} onTranskript={onTranskript} {...props} />);
  return { sdk, ladeSdk, onTranskript, ...ansicht };
}

const balken = () => screen.getAllByTestId("voice-balken") as HTMLElement[];
const hoehen = () => balken().map((b) => Number.parseFloat(b.style.height));
const knopf = () => screen.getByRole("button", { name: /Mit Stimme fragen/ });
const zustand = () => screen.getByTestId("voice-zustand").textContent;

async function klicke() {
  await act(async () => {
    fireEvent.click(knopf());
  });
}

async function imGespraech() {
  const z = zeige();
  await klicke();
  z.sdk.emit("call-start");
  return z;
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("VoiceKnopf Zustände", () => {
  it("ist ohne öffentlichen Schlüssel aus, deaktiviert und sagt, dass die Frage als Text geht", () => {
    zeige({ konfiguration: { publicKey: null, assistantId: "asst-test", aktiv: false } });
    expect(knopf()).toHaveProperty("disabled", true);
    expect(screen.getByText(VOICE_AUS_TEXT)).toBeTruthy();
    expect(knopf().getAttribute("aria-describedby")).toBe(screen.getByText(VOICE_AUS_TEXT).id);
  });

  it("ist ohne assistantId aus, auch wenn der Schlüssel vorliegt", () => {
    zeige({ konfiguration: { publicKey: "pk-test", assistantId: null, aktiv: false } });
    expect(knopf()).toHaveProperty("disabled", true);
    expect(screen.getByText(VOICE_AUS_TEXT)).toBeTruthy();
  });

  it("ist ohne SDK-Lader aus", () => {
    render(<VoiceKnopf konfiguration={aktiv} />);
    expect(knopf()).toHaveProperty("disabled", true);
  });

  it("holt die Konfiguration selbst und bleibt ohne Schlüssel aus", async () => {
    const holen = vi.fn(async () => Response.json({ publicKey: null, assistantId: null, aktiv: false }));
    vi.stubGlobal("fetch", holen);
    render(<VoiceKnopf ladeSdk={vi.fn()} />);
    expect(zustand()).toBe("Sprache wird geprüft");
    expect(await screen.findByText(VOICE_AUS_TEXT)).toBeTruthy();
    expect(holen).toHaveBeenCalledWith("/api/plattform/voice-config", expect.objectContaining({ cache: "no-store" }));
  });

  it("ist bereit mit Speicherhinweis und lädt das SDK erst beim Klick", async () => {
    const { ladeSdk } = zeige();
    expect(zustand()).toBe("Bereit");
    expect(knopf().getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByText(VOICE_SPEICHER_HINWEIS)).toBeTruthy();
    expect(ladeSdk).not.toHaveBeenCalled();
    await klicke();
    expect(ladeSdk).toHaveBeenCalledWith("pk-test");
    expect(zustand()).toBe("Verbindet");
  });

  // Fängt ab: ein Raum mit eigenem Assistenten startet lokal ohne Tunnel trotzdem einen Anruf.
  it("bleibt aus, wenn die Prop assistantId gesetzt ist, die Konfiguration aber aktiv false sagt", async () => {
    const { sdk, ladeSdk } = zeige({
      assistantId: "asst-raum",
      konfiguration: { publicKey: "pk-test", assistantId: null, aktiv: false },
    });
    expect(knopf()).toHaveProperty("disabled", true);
    expect(screen.getByText(VOICE_AUS_TEXT)).toBeTruthy();
    await klicke();
    expect(ladeSdk).not.toHaveBeenCalled();
    expect(sdk.start).not.toHaveBeenCalled();
  });

  it("startet mit der assistantId aus der Prop vor der aus der Konfiguration", async () => {
    const { sdk } = zeige({ assistantId: "asst-raum" });
    await klicke();
    expect(sdk.start).toHaveBeenCalledWith("asst-raum");
  });

  it("zeigt Hört zu mit Zeit, dann Denkt und Spricht", async () => {
    vi.useFakeTimers();
    const { sdk } = await imGespraech();
    expect(knopf().getAttribute("aria-pressed")).toBe("true");
    act(() => vi.advanceTimersByTime(7000));
    expect(zustand()).toBe("Hört zu · 0:07");
    sdk.emit("message", { type: "transcript", role: "user", transcriptType: "final", transcript: "Wie viele?" });
    expect(zustand()).toBe("Denkt");
    sdk.emit("speech-start");
    expect(zustand()).toBe("Spricht");
    sdk.emit("speech-end");
    expect(zustand()).toMatch(/^Hört zu · 0:0\d$/);
  });

  it("übernimmt den Pegel aus volume-level höchstens alle 340 ms und skaliert die Grundform", async () => {
    vi.useFakeTimers();
    const { sdk } = await imGespraech();
    sdk.emit("speech-start");
    sdk.emit("volume-level", 1);
    expect(hoehen()).toEqual(pegelHoehen(0));
    act(() => vi.advanceTimersByTime(PEGEL_TAKT_MS));
    expect(hoehen()).toEqual([...PEGEL_GRUNDFORM]);
    expect(balken()[0]?.className).toContain("bg-gruen");
    expect(PEGEL_TAKT_MS).toBeGreaterThanOrEqual(1000 / 3);
  });
});

describe("VoiceKnopf Pegel-Zeile (Frame eE7uh)", () => {
  it("hat 17 Balken mit der Grundform aus dem Frame, höchstens 24 px", () => {
    expect(PEGEL_GRUNDFORM).toEqual([6, 10, 16, 22, 14, 8, 18, 24, 12, 6, 16, 20, 10, 6, 14, 8, 4]);
    zeige();
    expect(balken()).toHaveLength(17);
    expect(Math.max(...PEGEL_GRUNDFORM)).toBe(24);
  });

  it("zeigt die Balken in bereit und aus flach in der Linienfarbe", () => {
    for (const konfiguration of [aktiv, { publicKey: null, assistantId: null, aktiv: false }]) {
      const { unmount } = zeige({ konfiguration });
      expect(hoehen()).toEqual(Array(17).fill(PEGEL_FLACH_PX));
      expect(balken().every((b) => b.className.includes("bg-line") && !b.className.includes("bg-gruen"))).toBe(true);
      unmount();
    }
  });

  it("erreicht bei Pegel 1 genau die Grundhöhe und fällt nie unter 3 px", () => {
    expect(pegelHoehen(1)).toEqual([...PEGEL_GRUNDFORM]);
    expect(Math.min(...pegelHoehen(0))).toBe(PEGEL_FLACH_PX);
    expect(pegelHoehen(0.5).every((h, i) => h <= PEGEL_GRUNDFORM[i]!)).toBe(true);
  });

  it("sagt ehrlich, wohin die Stimme geht und was gespeichert wird", () => {
    const text =
      "Sprechen oder tippen. Ihre Stimme geht live an den Sprachdienst Vapi in den USA. Hier gespeichert wird nur der Text.";
    zeige();
    expect(screen.getByText(text)).toBeTruthy();
    expect(VOICE_SPEICHER_HINWEIS).toBe(text);
  });
});

describe("VoiceKnopf Transkript", () => {
  it("ruft onTranskript nur für finale Transkripte", async () => {
    const { sdk, onTranskript } = await imGespraech();
    sdk.emit("message", { type: "transcript", role: "user", transcriptType: "partial", transcript: "Wie" });
    sdk.emit("message", { type: "status-update", status: "in-progress" });
    expect(onTranskript).not.toHaveBeenCalled();
    sdk.emit("message", { type: "transcript", role: "user", transcriptType: "final", transcript: " Wie viele? " });
    sdk.emit("message", { type: "transcript", role: "assistant", transcriptType: "final", transcript: "Drei." });
    // Fängt ab (#120): neuere SDK-Stände senden den Typ mit Zusatz; der Abschnitt ging dann verloren.
    sdk.emit("message", { type: 'transcript[transcriptType="final"]', role: "user", transcriptType: "final", transcript: "Und im April?" });
    expect(onTranskript.mock.calls).toEqual([
      [{ rolle: "nutzer", text: "Wie viele?" }],
      [{ rolle: "assistent", text: "Drei." }],
      [{ rolle: "nutzer", text: "Und im April?" }],
    ]);
  });
});

describe("VoiceKnopf Beenden", () => {
  it("beendet per zweitem Klick", async () => {
    const { sdk } = await imGespraech();
    await klicke();
    expect(sdk.stop).toHaveBeenCalledTimes(1);
    expect(zustand()).toBe("Bereit");
    expect(knopf().getAttribute("aria-pressed")).toBe("false");
  });

  it("beendet per Escape, auch wenn der Fokus woanders steht", async () => {
    const { sdk } = await imGespraech();
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(sdk.stop).toHaveBeenCalledTimes(1);
    expect(zustand()).toBe("Bereit");
  });

  it("bricht beim Verbinden per Escape ab und ignoriert ein spätes call-start", async () => {
    const z = zeige();
    await klicke();
    fireEvent.keyDown(document, { key: "Escape" });
    z.sdk.emit("call-start");
    expect(zustand()).toBe("Bereit");
  });

  it("schließt das Gespräch beim Verlassen der Seite", async () => {
    const { sdk, unmount } = await imGespraech();
    unmount();
    expect(sdk.stop).toHaveBeenCalled();
    expect(sdk.removeAllListeners).toHaveBeenCalled();
  });
});

function aufschub<T>() {
  let aufloesen!: (wert: T) => void;
  const zusage = new Promise<T>((r) => {
    aufloesen = r;
  });
  return { zusage, aufloesen };
}

async function loese<T>(a: { aufloesen: (wert: T) => void }, wert: T) {
  await act(async () => {
    a.aufloesen(wert);
    await new Promise((r) => setTimeout(r, 0));
  });
}

const abbrechen = {
  Escape: async () => {
    fireEvent.keyDown(document.body, { key: "Escape" });
  },
  "zweiter Klick": klicke,
};

// Fängt ab: Escape, zweiter Klick oder Verlassen der Seite während Laden oder Start beenden den Anruf nicht.
// Dann tritt er später doch bei, die Anzeige sagt „Bereit“, der Assistent spricht und die Minuten laufen.
describe("VoiceKnopf Abbruch während des Starts", () => {
  it.each(Object.entries(abbrechen))("%s während das SDK lädt: kein Start, SDK beendet, keine Listener", async (_, tue) => {
    const sdk = new FalschesSdk();
    const laden = aufschub<VoiceSdk>();
    zeige({ ladeSdk: vi.fn(() => laden.zusage) });
    await klicke();
    expect(zustand()).toBe("Verbindet");
    await tue();
    expect(zustand()).toBe("Bereit");
    await loese(laden, sdk);
    expect(sdk.start).not.toHaveBeenCalled();
    expect(sdk.stop).toHaveBeenCalled();
    expect(sdk.handler.size).toBe(0);
    expect(zustand()).toBe("Bereit");
  });

  it("Verlassen der Seite während das SDK lädt: kein Start, keine Listener", async () => {
    const sdk = new FalschesSdk();
    const laden = aufschub<VoiceSdk>();
    const { unmount } = zeige({ ladeSdk: vi.fn(() => laden.zusage) });
    await klicke();
    unmount();
    await loese(laden, sdk);
    expect(sdk.start).not.toHaveBeenCalled();
    expect(sdk.stop).toHaveBeenCalled();
    expect(sdk.handler.size).toBe(0);
  });

  it.each(Object.entries(abbrechen))("%s während start läuft: nach dem Start stop() und Listener weg", async (_, tue) => {
    const z = zeige();
    const start = aufschub<unknown>();
    z.sdk.start.mockImplementationOnce(() => start.zusage);
    await klicke();
    expect(z.sdk.start).toHaveBeenCalledTimes(1);
    await tue();
    const stopVorher = z.sdk.stop.mock.calls.length;
    await loese(start, { id: "anruf-1" });
    expect(z.sdk.stop.mock.calls.length).toBeGreaterThan(stopVorher);
    expect(z.sdk.removeAllListeners).toHaveBeenCalled();
    z.sdk.emit("call-start");
    expect(zustand()).toBe("Bereit");
  });

  it("Verlassen der Seite während start läuft: nach dem Start stop()", async () => {
    const z = zeige();
    const start = aufschub<unknown>();
    z.sdk.start.mockImplementationOnce(() => start.zusage);
    await klicke();
    z.unmount();
    const stopVorher = z.sdk.stop.mock.calls.length;
    await loese(start, { id: "anruf-1" });
    expect(z.sdk.stop.mock.calls.length).toBeGreaterThan(stopVorher);
    expect(z.sdk.removeAllListeners).toHaveBeenCalled();
  });

  // Fängt ab: das Abräumen des alten Starts beendet das neue Gespräch, das der Nutzer gleich danach beginnt.
  it("ein neuer Start nach dem Abbruch wartet auf den alten und läuft mit frischem SDK", async () => {
    const alt = new FalschesSdk();
    const neu = new FalschesSdk();
    const start = aufschub<unknown>();
    alt.start.mockImplementationOnce(() => start.zusage);
    const ladeSdk = vi.fn(async () => alt).mockResolvedValueOnce(alt).mockResolvedValueOnce(neu);
    render(<VoiceKnopf konfiguration={aktiv} ladeSdk={ladeSdk} />);
    await klicke();
    fireEvent.keyDown(document.body, { key: "Escape" });
    await klicke();
    expect(zustand()).toBe("Verbindet");
    await loese(start, { id: "anruf-alt" });
    expect(alt.removeAllListeners).toHaveBeenCalled();
    expect(neu.start).toHaveBeenCalledWith("asst-test");
    neu.emit("call-start");
    expect(zustand()).toMatch(/^Hört zu/);
    expect(neu.stop).not.toHaveBeenCalled();
  });
});

describe("VoiceKnopf Fehler", () => {
  // Fängt ab: ein fehlender Rauschfilter, eine fehlende Pegelanzeige oder Autoplay beenden das Gespräch,
  // Autoplay sogar als Mikrofon-Meldung. Laut SDK läuft der Anruf in diesen Fällen weiter.
  it.each(["audio-processing-setup-error", "audio-observer-setup-error", "audio-start-failed"])(
    "%s im Gespräch: Zustand bleibt Hört zu, kein stop()",
    async (art) => {
      const { sdk } = await imGespraech();
      sdk.emit("error", { type: art, error: { name: "NotAllowedError", message: "play() failed" } });
      expect(zustand()).toMatch(/^Hört zu/);
      expect(sdk.stop).not.toHaveBeenCalled();
      expect(screen.queryByText(VOICE_FEHLER_TEXT.mikrofon)).toBeNull();
    },
  );

  it("konfiguration: Route nicht erreichbar, Knopf gesperrt", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("kaputt", { status: 500 })));
    render(<VoiceKnopf ladeSdk={vi.fn()} />);
    expect(await screen.findByText(VOICE_FEHLER_TEXT.konfiguration)).toBeTruthy();
    expect(knopf()).toHaveProperty("disabled", true);
  });

  it("laden: SDK-Import schlägt fehl, erneuter Versuch bleibt möglich", async () => {
    zeige({ ladeSdk: vi.fn(async () => Promise.reject(new Error("chunk"))) });
    await klicke();
    expect(zustand()).toBe(VOICE_FEHLER_TEXT.laden);
    expect(knopf()).toHaveProperty("disabled", false);
  });

  it("mikrofon: start wirft NotAllowedError", async () => {
    const z = zeige();
    z.sdk.start.mockRejectedValueOnce(Object.assign(new Error("Permission denied"), { name: "NotAllowedError" }));
    await klicke();
    expect(zustand()).toBe(VOICE_FEHLER_TEXT.mikrofon);
  });

  it("mikrofon: Fehler-Ereignis mit verschachteltem Daily-Fehler beim Verbinden", async () => {
    const z = zeige();
    z.sdk.start.mockImplementationOnce(() => new Promise(() => undefined));
    await klicke();
    expect(zustand()).toBe("Verbindet");
    z.sdk.emit("error", { type: "start-method-error", error: { error: { name: "NotAllowedError" } } });
    expect(zustand()).toBe(VOICE_FEHLER_TEXT.mikrofon);
  });

  it("start: start liefert null ohne Fehler-Ereignis", async () => {
    const z = zeige();
    z.sdk.start.mockResolvedValueOnce(null);
    await klicke();
    expect(zustand()).toBe(VOICE_FEHLER_TEXT.start);
  });

  it("verbindung: Fehler-Ereignis im Gespräch beendet und bleibt nach call-end sichtbar", async () => {
    const { sdk } = await imGespraech();
    sdk.emit("error", { type: "daily-error", error: { message: "Meeting has ended" } });
    sdk.emit("call-end");
    expect(zustand()).toBe(VOICE_FEHLER_TEXT.verbindung);
    expect(sdk.stop).toHaveBeenCalled();
    expect(knopf().getAttribute("aria-pressed")).toBe("false");
  });
});

describe("VoiceKnopf Vorschau", () => {
  it("zeigt einen gesetzten Zustand ohne SDK und ohne Abruf", () => {
    const holen = vi.fn();
    vi.stubGlobal("fetch", holen);
    render(<VoiceKnopf vorschau={{ zustand: "hoert", pegel: 0.4, sekunden: 7 }} />);
    expect(zustand()).toBe("Hört zu · 0:07");
    expect(hoehen()).toEqual(pegelHoehen(0.4));
    expect(holen).not.toHaveBeenCalled();
  });
});
