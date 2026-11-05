import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ereignisseJson from "../../../app/api/uc2/_fixtures/ereignisse-mock.json";
import { useEntscheidung } from "../freigabe";
import { PanelBuehne } from "./buehne";

vi.mock("next/link", () => ({ default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a> }));

const alle = ereignisseJson as unknown as { seq: number; art: string }[];

/** EventSource-Ersatz: liefert die gegebenen Ereignisse und schließt dann wie ein abgerissener Server. */
class FakeQuelle {
  static CLOSED = 2;
  static letzte: FakeQuelle | null = null;
  readyState = 1;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private hoerer = new Map<string, ((e: MessageEvent<string>) => void)[]>();
  constructor(public url: string) {
    FakeQuelle.letzte = this;
  }
  addEventListener(art: string, f: (e: MessageEvent<string>) => void) {
    this.hoerer.set(art, [...(this.hoerer.get(art) ?? []), f]);
  }
  sende(ereignisse: { art: string }[]) {
    for (const e of ereignisse) for (const f of this.hoerer.get(e.art) ?? []) f({ data: JSON.stringify(e) } as MessageEvent<string>);
  }
  abreissen() {
    this.readyState = FakeQuelle.CLOSED;
    this.onerror?.();
  }
  close() {
    this.readyState = FakeQuelle.CLOSED;
  }
}

beforeEach(() => {
  vi.stubGlobal("EventSource", FakeQuelle);
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({})));
});
afterEach(() => vi.unstubAllGlobals());

it("KI-Kennzeichnung steht ab dem ersten Zug, nicht erst im Abschluss", async () => {
  render(<PanelBuehne fallId="mock-wartezeiten" modus="vorfuehrung" />);
  act(() => FakeQuelle.letzte!.sende(alle.slice(0, 7)));
  await waitFor(() => expect(screen.getByTestId("uc2-modell-satz").textContent).toContain("ohne Sprachmodell"));
});

it("abgerissene Verbindung: ein Satz und „Neu verbinden“, das Gezeigte bleibt", async () => {
  render(<PanelBuehne fallId="mock-wartezeiten" modus="vorfuehrung" />);
  const erste = FakeQuelle.letzte!;
  act(() => {
    erste.sende(alle.slice(0, 10));
    erste.abreissen();
  });
  expect((await screen.findByRole("alert")).textContent).toContain("Verbindung ist unterbrochen");
  await userEvent.click(screen.getByRole("button", { name: "Neu verbinden" }));
  expect(FakeQuelle.letzte).not.toBe(erste);
});

it("live lädt die gespeicherte Freigabe aus dem Bericht, statt wieder das Formular zu zeigen", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({ freigabe: { name: "Erika Muster", zeit: "2026-11-05T17:00:00Z", entscheidung: "freigegeben" } })),
  );
  const { result } = renderHook(() => useEntscheidung("15", "live", true));
  await waitFor(() => expect(result.current[0]).toMatchObject({ art: "freigegeben", name: "Erika Muster" }));
});

it("in der Vorführung fragt die Freigabe den Server nicht", () => {
  const f = vi.fn();
  vi.stubGlobal("fetch", f);
  renderHook(() => useEntscheidung("mock-wartezeiten", "vorfuehrung", true));
  expect(f).not.toHaveBeenCalled();
});

it("live behauptet vor dem Start-Ereignis nicht „ohne Sprachmodell“", () => {
  render(<PanelBuehne fallId="15" modus="live" />);
  expect(screen.getByTestId("uc2-modell-satz").textContent).toBe("Die Verhandlung startet.");
});

it("„Zum Ergebnis“ zeigt mit einem Klick das Ende, auch wenn die Aufzeichnung noch nicht ganz da ist", async () => {
  // Fängt den Live-Test 05.11.: Der Klick sprang nur bis zum bisher Angekommenen, es brauchte drei Klicks.
  render(<PanelBuehne fallId="mock-wartezeiten" modus="vorfuehrung" />);
  const erste = FakeQuelle.letzte!;
  act(() => erste.sende(alle.slice(0, 10)));
  await userEvent.click(screen.getByRole("button", { name: "Zum Ergebnis" }));

  const zweite = FakeQuelle.letzte!;
  expect(zweite).not.toBe(erste);
  expect(zweite.url).toContain("sofort=1");
  expect(zweite.url).toContain(`seq=${alle[9]!.seq}`);
  act(() => zweite.sende(alle.slice(10)));
  await waitFor(() => expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("Ergebnis nach"));
  expect(screen.queryByRole("button", { name: "Zum Ergebnis" })).toBeNull();
});

it("„Zum Ergebnis“ wirkt auch, wenn beim Klick noch nichts angekommen ist", async () => {
  // Fängt den Browser-Lauf 05.11.: Der Klick kam vor dem ersten Ereignis, danach lief die Bühne im Takt weiter.
  render(<PanelBuehne fallId="mock-wartezeiten" modus="vorfuehrung" />);
  await userEvent.click(screen.getByRole("button", { name: "Zum Ergebnis" }));
  const quelle = FakeQuelle.letzte!;
  for (const ereignis of alle) act(() => quelle.sende([ereignis]));
  act(() => quelle.sende([{ art: "ende" }]));
  await waitFor(() => expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("Ergebnis nach"));
});
