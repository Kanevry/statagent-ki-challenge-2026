import { act, render, screen } from "@testing-library/react";
import ereignisseJson from "../../app/api/uc2/_fixtures/ereignisse-mock.json";
import { useEreignisstrom } from "./use-ereignisstrom";

// Ein EventSource-Ersatz, den der Test von Hand füttert. Fängt ab: Ereignisse, die nach "ende" noch zählen,
// eine Wiederverbindung ohne ?seq= und eine Verbindung, die nie geschlossen wird.

class Quelle {
  static alle: Quelle[] = [];
  static readonly CLOSED = 2;
  readonly url: string;
  readyState = 1;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  geschlossen = false;
  private hoerer = new Map<string, ((e: Event) => void)[]>();
  constructor(url: string) {
    this.url = url;
    Quelle.alle.push(this);
  }
  addEventListener(art: string, f: (e: Event) => void) {
    this.hoerer.set(art, [...(this.hoerer.get(art) ?? []), f]);
  }
  close() {
    this.geschlossen = true;
    this.readyState = 2;
  }
  sende(art: string, daten: unknown) {
    for (const f of this.hoerer.get(art) ?? []) f(new MessageEvent(art, { data: JSON.stringify(daten) }));
  }
}

function Anzeige({ id }: { id: string }) {
  const { zustand, verbindung, neuVerbinden } = useEreignisstrom(id);
  return (
    <div>
      <p data-testid="s">{`${zustand.status}|${zustand.letzteSeq}|${verbindung}`}</p>
      <button onClick={neuVerbinden}>neu</button>
    </div>
  );
}

const alle = ereignisseJson as { seq: number; art: string }[];

beforeEach(() => {
  Quelle.alle = [];
  vi.stubGlobal("EventSource", Quelle);
});
afterEach(() => vi.unstubAllGlobals());

it("liest den Strom, ordnet Nummern, schließt bei ende und nimmt danach nichts mehr an", () => {
  const { unmount } = render(<Anzeige id="mock-wartezeiten" />);
  const q = Quelle.alle[0]!;
  expect(q.url).toBe("/api/uc2/faelle/mock-wartezeiten/ereignisse");
  act(() => q.onopen?.());
  act(() => {
    for (const e of alle) q.sende(e.art, e);
  });
  expect(screen.getByTestId("s").textContent).toBe("fertig|66|offen");
  act(() => q.sende("ende", { status: "fertig" }));
  expect(screen.getByTestId("s").textContent).toBe("fertig|67|zu");
  expect(q.geschlossen).toBe(true);
  unmount();
});

it("verbindet nach einem Abbruch ab der letzten Nummer neu", () => {
  render(<Anzeige id="mock-wartezeiten" />);
  const q = Quelle.alle[0]!;
  act(() => {
    for (const e of alle.slice(0, 12)) q.sende(e.art, e);
  });
  q.readyState = 2;
  act(() => q.onerror?.());
  expect(screen.getByTestId("s").textContent).toBe("laeuft|12|unterbrochen");
  act(() => screen.getByRole("button", { name: "neu" }).click());
  expect(Quelle.alle[1]?.url).toBe("/api/uc2/faelle/mock-wartezeiten/ereignisse?seq=12");
  expect(Quelle.alle[0]?.geschlossen).toBe(true);
});

it("meldet 'verbindet', solange der Browser selbst neu versucht", () => {
  render(<Anzeige id="x" />);
  const q = Quelle.alle[0]!;
  q.readyState = 0;
  act(() => q.onerror?.());
  expect(screen.getByTestId("s").textContent).toContain("verbindet");
});

it("ein 404 auf den Fall meldet nicht-gefunden statt unterbrochen", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 404 })));
  render(<Anzeige id="gibt-es-nicht" />);
  const q = Quelle.alle[0]!;
  q.readyState = 2;
  await act(async () => q.onerror?.());
  expect(screen.getByTestId("s").textContent).toBe("wartet|0|nicht-gefunden");
});

it("ein Fall, den es gibt, aber ohne Strom, bleibt unterbrochen", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({}, { status: 200 })));
  render(<Anzeige id="17" />);
  const q = Quelle.alle[0]!;
  q.readyState = 2;
  await act(async () => q.onerror?.());
  expect(screen.getByTestId("s").textContent).toBe("wartet|0|unterbrochen");
});
