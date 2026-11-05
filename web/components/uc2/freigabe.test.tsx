import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ereignisseJson from "../../app/api/uc2/_fixtures/ereignisse-mock.json";
import { entscheidungAusBericht, StandMitFreigabe, VORFUEHRUNG_HINWEIS, VORFUEHRUNG_SATZ, type Speichern } from "./freigabe";
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
    "Mit Ihrem Namen gilt das Ergebnis als geprüft und steht im Protokoll.",
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

it("lehnt mit Begründung ab: Abgelehnt von Name, die Marke Entwurf wird zu Abgelehnt", async () => {
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
  // Statt „Entwurf“ steht die Marke „Abgelehnt“ am Ergebnis.
  expect(screen.queryByTestId("uc2-entwurf")).toBeNull();
  expect(document.querySelector('[data-spur="stand"] [data-testid="uc2-abgelehnt"]')?.textContent).toBe("Abgelehnt");
});

it("nach einer Freigabe steht keine Marke mehr am Ergebnis", async () => {
  zeige("live", vi.fn<Speichern>(async () => ({ zeitpunkt: "2026-11-05T16:30:00+00:00" })));
  await userEvent.type(screen.getByLabelText("Vor- und Nachname"), NAME);
  await userEvent.click(screen.getByRole("button", { name: "Freigeben" }));
  await waitFor(() => expect(screen.getByTestId("uc2-freigabe").getAttribute("data-zustand")).toBe("freigegeben"));
  expect(screen.queryByTestId("uc2-entwurf")).toBeNull();
  expect(screen.queryByTestId("uc2-abgelehnt")).toBeNull();
});

it("alle Knöpfe der Karte sind mindestens 44 px hoch (min-h-11), auch Ablehnen und Zurück", async () => {
  zeige("live", vi.fn());
  const hoch = (name: string) => screen.getByRole("button", { name }).className;
  expect(hoch("Freigeben")).toContain("min-h-11");
  expect(hoch("Ablehnen")).toContain("min-h-11");
  await userEvent.click(screen.getByRole("button", { name: "Ablehnen" }));
  expect(hoch("Ablehnung speichern")).toContain("min-h-11");
  expect(hoch("Zurück")).toContain("min-h-11");
});

it("das Begründungsfeld nimmt höchstens 500 Zeichen an", async () => {
  zeige("live", vi.fn());
  await userEvent.click(screen.getByRole("button", { name: "Ablehnen" }));
  expect(screen.getByLabelText("Begründung der Ablehnung").getAttribute("maxlength")).toBe("500");
});

it("live: der Satz verspricht den Namen im Protokoll; in der Vorführung sagt er, dass nichts gespeichert wird", () => {
  const live = zeige("live", vi.fn());
  expect(screen.getByTestId("uc2-freigabe").textContent).toContain("steht im Protokoll");
  live.unmount();
  zeige("vorfuehrung");
  const text = screen.getByTestId("uc2-freigabe").textContent!;
  expect(VORFUEHRUNG_SATZ).toContain("In der Vorführung wird nichts gespeichert.");
  expect(text).toContain(VORFUEHRUNG_SATZ);
  expect(text).not.toContain("Mit Ihrem Namen gilt das Ergebnis als geprüft und steht im Protokoll.");
});

it("öffentlicher Bericht ohne Name und Grund: „Freigegeben am <Zeit>“ bzw. „Abgelehnt am <Zeit>“", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({ freigabe: { zeit: "2026-11-05T16:30:00+00:00", entscheidung: "abgelehnt" } })),
  );
  zeige("live");
  await waitFor(() => expect(screen.getByTestId("uc2-freigabe").textContent).toContain("Abgelehnt am 05.11.2026, 17:30"));
  const text = screen.getByTestId("uc2-freigabe").textContent!;
  expect(text).not.toContain(" von ");
  expect(text).not.toContain("Begründung");
  expect(screen.getByTestId("uc2-abgelehnt")).toBeTruthy();
  expect(screen.queryByTestId("uc2-entwurf")).toBeNull();
});

it("Vorführmodus: die Freigabe wirkt in der Seite, ruft den Server nicht auf und sagt danach, dass nichts gespeichert ist", async () => {
  const speichern = vi.fn<Speichern>();
  zeige("vorfuehrung", speichern);
  // Vor der Entscheidung sagt es der Satz über dem Formular; zweimal wäre zu viel.
  expect(screen.queryByTestId("uc2-freigabe-vorfuehrung")).toBeNull();
  await userEvent.type(screen.getByLabelText("Vor- und Nachname"), NAME);
  await userEvent.click(screen.getByRole("button", { name: "Freigeben" }));
  await waitFor(() => expect(screen.getByTestId("uc2-freigabe").textContent).toContain(`Freigegeben von ${NAME}`));
  expect(screen.queryByTestId("uc2-entwurf")).toBeNull();
  expect(speichern).not.toHaveBeenCalled();
  expect(fetch).not.toHaveBeenCalled();
  // Der Satz ist nach der Freigabe weg, der Hinweis trägt es nun allein.
  expect(screen.getByTestId("uc2-freigabe-vorfuehrung").textContent).toBe(VORFUEHRUNG_HINWEIS);
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

it("entscheidungAusBericht liest öffentliche Entscheidungen ohne Namen", () => {
  expect(entscheidungAusBericht({ freigabe: { zeit: "z", entscheidung: "freigegeben" } })).toEqual({ art: "freigegeben", zeit: "z" });
  expect(entscheidungAusBericht({ freigabe: { zeit: "z", entscheidung: "abgelehnt" } })).toEqual({ art: "abgelehnt", zeit: "z" });
  expect(entscheidungAusBericht({ freigabe: { name: NAME, entscheidung: "freigegeben" } })).toBeNull();
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
