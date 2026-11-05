import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ereignisseJson from "../../app/api/uc2/_fixtures/ereignisse-mock.json";
import { entscheidungAusBericht, StandMitFreigabe, VORFUEHRUNG_HINWEIS, type Speichern } from "./freigabe";
import { ableiten } from "./zustand";

// Freigabe des Berichts (U2-2): "Entwurf" bis ein Mensch mit Vor- und Nachnamen freigibt, danach "Freigegeben von …".
// Die Beispielnamen sind erfunden; "Musterfrau" ginge nicht, die Namensregel lehnt "muster" als Platzhalter ab.

const fertig = ableiten(ereignisseJson as unknown[]);
const NAME = "Maria Beispiel";

function zeige(modus: "live" | "vorfuehrung", speichern?: Speichern) {
  return render(<StandMitFreigabe zustand={fertig} fallId={modus === "live" ? "42" : "mock-wartezeiten"} modus={modus} speichern={speichern} />);
}

beforeEach(() => {
  // Live fragt die Seite den Bericht nach einer früheren Entscheidung; hier gibt es keine.
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({ freigabe: null })));
});
afterEach(() => vi.unstubAllGlobals());

it("zeigt vor der Freigabe die Marke Entwurf am Ergebnis und die Freigabe-Karte mit dem Satz", () => {
  zeige("live", vi.fn());
  const stand = document.querySelector('[data-spur="stand"]')!;
  expect(stand.querySelector('[data-testid="uc2-entwurf"]')?.textContent).toBe("Entwurf");
  expect(stand.querySelector("h2")?.textContent).toBe("Am Ende gilt");
  expect(screen.getByTestId("uc2-freigabe").textContent).toContain(
    "Das Ergebnis der Verhandlung wird als geprüft markiert und kommt mit deinem Namen ins Protokoll.",
  );
  expect(screen.getByRole("button", { name: "Freigeben" })).toHaveProperty("disabled", true);
  expect(screen.queryByTestId("uc2-freigabe-vorfuehrung")).toBeNull();
});

it("zeigt keine Freigabe, solange das Ergebnis nicht steht", () => {
  render(<StandMitFreigabe zustand={{ ...fertig, status: "laeuft" }} fallId="42" modus="live" />);
  expect(screen.queryByTestId("uc2-entwurf")).toBeNull();
  expect(screen.queryByTestId("uc2-freigabe")).toBeNull();
});

it("gibt mit gültigem Namen frei: Name und Zeit des Servers stehen da, die Marke ist weg", async () => {
  const speichern = vi.fn<Speichern>(async () => ({ zeitpunkt: "2026-11-05T16:30:00+00:00" }));
  zeige("live", speichern);
  await userEvent.type(screen.getByLabelText("Vor- und Nachname"), `  ${NAME} `);
  await userEvent.click(screen.getByRole("button", { name: "Freigeben" }));
  await waitFor(() => expect(screen.getByTestId("uc2-freigabe").getAttribute("data-zustand")).toBe("freigegeben"));
  expect(speichern).toHaveBeenCalledExactlyOnceWith({ name: NAME, entscheidung: "freigegeben" });
  expect(screen.getByTestId("uc2-freigabe").textContent).toContain(`Freigegeben von ${NAME}, 05.11.2026, 17:30`);
  expect(screen.queryByTestId("uc2-entwurf")).toBeNull();
  expect(screen.queryByLabelText("Vor- und Nachname")).toBeNull();
});

it("lehnt den Namen Team ab: Grund beim Tippen, Knopf gesperrt, nichts gespeichert", async () => {
  const speichern = vi.fn<Speichern>();
  zeige("live", speichern);
  const feld = screen.getByLabelText("Vor- und Nachname");
  await userEvent.type(feld, "Team");
  expect(screen.getByRole("button", { name: "Freigeben" })).toHaveProperty("disabled", true);
  await userEvent.type(feld, " Wien");
  expect(document.body.textContent).toContain("Bitte den eigenen Namen eingeben, keine Rolle.");
  expect(screen.getByRole("button", { name: "Freigeben" })).toHaveProperty("disabled", true);
  await userEvent.type(feld, "{Enter}");
  expect(speichern).not.toHaveBeenCalled();
  expect(screen.getByTestId("uc2-entwurf")).toBeTruthy();
});

it("zeigt einen Fehler des Servers und bleibt Entwurf", async () => {
  zeige("live", async () => {
    throw new Error("Dieser Bericht ist noch nicht fertig oder schon entschieden.");
  });
  await userEvent.type(screen.getByLabelText("Vor- und Nachname"), NAME);
  await userEvent.click(screen.getByRole("button", { name: "Freigeben" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Nicht gespeichert. Dieser Bericht ist noch nicht fertig");
  expect(screen.getByTestId("uc2-entwurf")).toBeTruthy();
});

it("lehnt mit Begründung ab: Abgelehnt von Name, die Marke ist weg", async () => {
  const speichern = vi.fn<Speichern>(async () => ({ zeitpunkt: "2026-11-05T16:30:00+00:00" }));
  zeige("live", speichern);
  await userEvent.type(screen.getByLabelText("Vor- und Nachname"), NAME);
  await userEvent.click(screen.getByRole("button", { name: "Ablehnen" }));
  expect(screen.getByRole("button", { name: "Ablehnung speichern" })).toHaveProperty("disabled", true);
  await userEvent.type(screen.getByLabelText("Begründung der Ablehnung"), "Zahlen zu dünn");
  await userEvent.click(screen.getByRole("button", { name: "Ablehnung speichern" }));
  await waitFor(() => expect(screen.getByTestId("uc2-freigabe").getAttribute("data-zustand")).toBe("abgelehnt"));
  expect(speichern).toHaveBeenCalledExactlyOnceWith({ name: NAME, entscheidung: "abgelehnt", begruendung: "Zahlen zu dünn" });
  const text = screen.getByTestId("uc2-freigabe").textContent!;
  expect(text).toContain(`Abgelehnt von ${NAME}, 05.11.2026, 17:30`);
  expect(text).toContain("Begründung: Zahlen zu dünn");
  expect(screen.queryByTestId("uc2-entwurf")).toBeNull();
});

it("Vorführmodus: der Hinweis steht da, die Freigabe wirkt in der Seite und ruft den Server nicht auf", async () => {
  const speichern = vi.fn<Speichern>();
  zeige("vorfuehrung", speichern);
  expect(screen.getByTestId("uc2-freigabe-vorfuehrung").textContent).toBe(VORFUEHRUNG_HINWEIS);
  expect(VORFUEHRUNG_HINWEIS).toBe("Vorführung: nichts gespeichert");
  await userEvent.type(screen.getByLabelText("Vor- und Nachname"), NAME);
  await userEvent.click(screen.getByRole("button", { name: "Freigeben" }));
  await waitFor(() => expect(screen.getByTestId("uc2-freigabe").textContent).toContain(`Freigegeben von ${NAME}`));
  expect(screen.queryByTestId("uc2-entwurf")).toBeNull();
  expect(speichern).not.toHaveBeenCalled();
  expect(fetch).not.toHaveBeenCalled();
  // Der Hinweis bleibt auch nach der Freigabe stehen.
  expect(screen.getByTestId("uc2-freigabe-vorfuehrung")).toBeTruthy();
});

it("live: eine frühere Entscheidung aus dem Bericht ersetzt Entwurf und Eingabe", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      Response.json({ freigabe: { name: NAME, zeit: "2026-11-05T16:30:00+00:00", entscheidung: "freigegeben", begruendung: null } }),
    ),
  );
  zeige("live");
  await waitFor(() => expect(screen.getByTestId("uc2-freigabe").textContent).toContain(`Freigegeben von ${NAME}`));
  expect(screen.queryByTestId("uc2-entwurf")).toBeNull();
  expect(screen.queryByLabelText("Vor- und Nachname")).toBeNull();
});

it("entscheidungAusBericht liest nur vollständige Entscheidungen", () => {
  expect(entscheidungAusBericht({ freigabe: null })).toBeNull();
  expect(entscheidungAusBericht({ freigabe: { name: NAME, zeit: "x", entscheidung: "vielleicht" } })).toBeNull();
  expect(entscheidungAusBericht({ freigabe: { name: NAME, zeit: "z", entscheidung: "abgelehnt", begruendung: "g" } })).toEqual({
    art: "abgelehnt",
    name: NAME,
    zeit: "z",
    begruendung: "g",
  });
});

it("zeigt im sichtbaren Text keine Gedankenstriche", () => {
  zeige("vorfuehrung");
  expect(screen.getByTestId("uc2-freigabe").textContent).not.toMatch(/[–—]/);
});
