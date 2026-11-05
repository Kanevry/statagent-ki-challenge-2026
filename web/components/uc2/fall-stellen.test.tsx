import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Vorbereitung } from "../../app/api/uc2/_lib/vorbereitung";
import { FallStellen } from "./fall-stellen";

const schieben = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: schieben, replace: vi.fn() }) }));

const akteure = [
  ["aerztekammer", 5, true],
  ["finanzministerium", 3, true],
  ["gesundheitsministerium", 6, true],
  ["patienten", 5, true],
  ["sv", 6, true],
  ["vertragsaerzte", 4, true],
  ["laender", 4, false],
  ["pharma", 0, false],
].map(([akteur, belegzahl, vorgeschlagen]) => ({ akteur, belegzahl, vorgeschlagen })) as Vorbereitung["akteure"];

const vorbereitung: Vorbereitung = {
  modus: "vorfuehrung",
  fall: { id: "wartezeiten", frage: "Wie können die Wartezeiten sinken?", stichtag: "2026-09-30", paket: "Paket A", maxAkteure: 6 },
  akteure,
  modelle: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
  schieben.mockClear();
});

const boxen = () => screen.getAllByRole("checkbox") as HTMLInputElement[];

it("zeigt die Frage, die Akteure mit Belegzahl und den Hinweis auf den aufgezeichneten Fall", () => {
  render(<FallStellen vorbereitung={vorbereitung} />);
  expect(screen.getByTestId("uc2-frage").textContent).toBe("Wie können die Wartezeiten sinken?");
  expect(boxen()).toHaveLength(8);
  expect(screen.getByLabelText(/Ärztekammer/).closest("label")?.textContent).toContain("5 Belege");
  expect(screen.getByLabelText(/Pharma/).closest("label")?.textContent).toContain("0 Belege");
  expect(screen.getByTestId("uc2-zaehler").textContent).toContain("6 von 6 gewählt");
  expect(screen.getByText("Presseartikel bis")).toBeTruthy();
});

it("Vorführmodus: ein ruhiger Hinweis, kein Fehlertext; live: kein Hinweis", () => {
  const { unmount } = render(<FallStellen vorbereitung={vorbereitung} />);
  expect(screen.getAllByTestId("uc2-vorfuehrung")).toHaveLength(1);
  expect(screen.getByTestId("uc2-vorfuehrung").textContent).toBe("Vorführmodus: Es läuft eine aufgezeichnete Verhandlung ohne Sprachmodell.");
  expect(document.body.textContent).not.toContain("nicht erreichbar");
  expect(document.querySelector("[role=alert]")).toBeNull();
  unmount();
  render(<FallStellen vorbereitung={{ ...vorbereitung, modus: "live" }} />);
  expect(screen.queryByTestId("uc2-vorfuehrung")).toBeNull();
});

it("lässt höchstens sechs Haken zu und gibt den Platz frei, wenn einer herausgenommen wird", async () => {
  const user = userEvent.setup();
  render(<FallStellen vorbereitung={vorbereitung} />);
  expect(boxen().filter((b) => b.checked)).toHaveLength(6);
  expect(boxen().filter((b) => b.disabled)).toHaveLength(2);
  await user.click(screen.getByLabelText(/Pharma/)); // gesperrt: keine Wirkung
  expect(boxen().filter((b) => b.checked)).toHaveLength(6);
  await user.click(screen.getByLabelText(/Finanzministerium/));
  expect(boxen().filter((b) => b.disabled)).toHaveLength(0);
  await user.click(screen.getByLabelText(/Pharma/));
  expect(screen.getByTestId("uc2-zaehler").textContent).toContain("6 von 6 gewählt");
});

it("Start schickt die Auswahl an /api/uc2/faelle und öffnet das Panel des neuen Falls", async () => {
  const user = userEvent.setup();
  const abruf = vi.fn(async (_u: string, _o?: RequestInit) => Response.json({ fall_id: "mock-wartezeiten", status: "laeuft" }, { status: 202 }));
  vi.stubGlobal("fetch", abruf);
  render(<FallStellen vorbereitung={vorbereitung} />);
  await user.click(screen.getByTestId("uc2-start"));
  await vi.waitFor(() => expect(schieben).toHaveBeenCalledWith("/uc2/panel?fall=mock-wartezeiten"));
  expect(abruf.mock.calls[0]?.[0]).toBe("/api/uc2/faelle");
  expect(JSON.parse(String(abruf.mock.calls[0]?.[1]?.body))).toEqual({
    fall: "wartezeiten",
    akteure: ["aerztekammer", "finanzministerium", "gesundheitsministerium", "patienten", "sv", "vertragsaerzte"],
  });
});

it("Hat die API die Auswahl abgelehnt, geht der Hinweis mit ins Panel", async () => {
  const user = userEvent.setup();
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({ fall_id: "7", status: "laeuft" }, { status: 202, headers: { "x-uc2-akteure": "ignoriert" } })),
  );
  render(<FallStellen vorbereitung={vorbereitung} />);
  await user.click(screen.getByTestId("uc2-start"));
  await vi.waitFor(() => expect(schieben).toHaveBeenCalledWith("/uc2/panel?fall=7&akteure=ignoriert"));
});

it("eine 422-Antwort der API zeigt eine klare Meldung, kein stilles Scheitern", async () => {
  const user = userEvent.setup();
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({ detail: [{ msg: "x" }] }, { status: 422 })));
  render(<FallStellen vorbereitung={vorbereitung} />);
  await user.click(screen.getByTestId("uc2-start"));
  expect((await screen.findByRole("alert")).textContent).toContain("Das Panel hat die Anfrage abgelehnt");
  expect(schieben).not.toHaveBeenCalled();
});

it("Start ist mit weniger als zwei Gruppen gesperrt", async () => {
  const user = userEvent.setup();
  render(<FallStellen vorbereitung={vorbereitung} />);
  for (const b of boxen().filter((x) => x.checked).slice(0, 5)) await user.click(b);
  expect((screen.getByTestId("uc2-start") as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText(/mindestens zwei Gruppen/)).toBeTruthy();
});

it.each([
  [403, "Online-Demo"],
  [405, "Online-Demo"],
  [409, "läuft schon eine Verhandlung"],
])("Start mit Status %i zeigt eine Meldung statt eines Absturzes", async (status, text) => {
  const user = userEvent.setup();
  vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status })));
  render(<FallStellen vorbereitung={vorbereitung} />);
  await user.click(screen.getByTestId("uc2-start"));
  expect((await screen.findByRole("alert")).textContent).toContain(text);
  expect(schieben).not.toHaveBeenCalled();
});

it("ein Netzfehler beim Start zeigt eine Meldung", async () => {
  const user = userEvent.setup();
  vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("offline"))));
  render(<FallStellen vorbereitung={vorbereitung} />);
  await user.click(screen.getByTestId("uc2-start"));
  expect((await screen.findByRole("alert")).textContent).toContain("Keine Verbindung");
});

it("der sichtbare Text hat keinen Geviertstrich und keinen Halbgeviertstrich", () => {
  render(<FallStellen vorbereitung={vorbereitung} />);
  expect(document.body.textContent).not.toMatch(/[—–]/);
});
