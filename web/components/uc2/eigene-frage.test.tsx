import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach } from "vitest";
import { EigeneFrage, KENNZEICHNUNG } from "./eigene-frage";
import { gliedere } from "./eigene-frage-text";

const TEXT = [
  "Zu dieser Frage gibt es kein Rechenmodell, deshalb stehen hier keine berechneten Zahlen.",
  "Wer ist dafür, wer dagegen:",
  "- Ärztekammer: Dafür bei: „Impfen in Apotheken“. Grund: Mehr Hilfe vor Ort. Beleg: Kurier, August 2026.",
  "- Sozialversicherung: Grund: Eine Ergänzung.",
  "- Pflege: Dafür bei: „Schutz“. Beleg: Kurier, Mai 2026.",
  "- Patient:innenvertretung: Dafür bei: „Schutz“. Grund: Klare Regeln. Beispielbeleg, erfunden: Beispielblatt, Juli 2026.",
  "So stehen die Beteiligten zu den Themen: Impfen in Apotheken: noch strittig; Schutz: alle dafür.",
  "Kurz gesagt: Bei diesem Thema sind sich alle einig.",
  "Bedingungen: Ärztekammer: Klare Leitung.; Sozialversicherung: Klare Regeln",
].join("\n");

// Wie im aktuellen Chrome: Der Aufruf liefert ein Promise, ein Effect darf es nicht zurückgeben.
Element.prototype.scrollIntoView = (() => Promise.resolve()) as unknown as Element["scrollIntoView"];
afterEach(() => vi.unstubAllGlobals());

function antwortet(status: number, daten: unknown) {
  const abruf = vi.fn(async () => new Response(JSON.stringify(daten), { status }));
  vi.stubGlobal("fetch", abruf);
  return abruf;
}

it("gliedert Stimmen, Quelle, Kurzfassung und Bedingungen; Unbekanntes bleibt stehen", () => {
  const g = gliedere(TEXT);
  expect(g.themen).toEqual([{ thema: "Impfen in Apotheken", stand: "noch strittig" }, { thema: "Schutz", stand: "alle dafür" }]);
  expect(g.stimmen[0]).toEqual({ name: "Ärztekammer", haltung: "Dafür bei: „Impfen in Apotheken“.", grund: "Mehr Hilfe vor Ort.", beleg: "Kurier, August 2026", ohneArtikel: false });
  expect(g.stimmen[1]).toEqual({ name: "Sozialversicherung", haltung: "", grund: "Eine Ergänzung.", beleg: null, ohneArtikel: false });
  expect(g.stimmen[2]).toEqual({ name: "Pflege", haltung: "Dafür bei: „Schutz“.", grund: "", beleg: "Kurier, Mai 2026", ohneArtikel: false });
  expect(g.stimmen[3]?.beleg).toBe("Beispiel, erfunden: Beispielblatt, Juli 2026");
  expect(g.bedingungen).toHaveLength(2);
  expect(g.rest).toEqual(["Zu dieser Frage gibt es kein Rechenmodell, deshalb stehen hier keine berechneten Zahlen."]);
});

it("schickt nur die Station uc2 und zeigt die Antwort mit Kennzeichnung", async () => {
  const abruf = antwortet(200, { antworten: [{ text: TEXT, belege: [], zahlen: [], uc: "uc2", modell: "m", protokoll_id: null }], fehlend: [] });
  render(<EigeneFrage />);
  expect(screen.getByText(/keine persönlichen Daten/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Ihre Frage"), { target: { value: "  Sollen Apotheken impfen?  " } });
  fireEvent.click(screen.getByRole("button", { name: "Abwägen lassen" }));
  const bereich = await screen.findByTestId("uc2-eigene-antwort");
  expect(bereich.textContent).toContain(KENNZEICHNUNG);
  expect(bereich.textContent).toContain("Quelle: Kurier, August 2026");
  const [ziel, optionen] = abruf.mock.calls[0] as unknown as [string, { body: string }];
  expect(ziel).toBe("/api/uc4/frage?station=uc2");
  expect(JSON.parse(optionen.body)).toEqual({ frage: "Sollen Apotheken impfen?" });
});

it("zeigt die Meldung der Route (Budget, Ratenlimit) und fragt ohne Text gar nicht", async () => {
  const abruf = antwortet(429, { fehler: "Das Tageskontingent ist aufgebraucht." });
  render(<EigeneFrage />);
  fireEvent.click(screen.getByRole("button", { name: "Abwägen lassen" }));
  expect(screen.getByText("Bitte eine Frage eingeben.")).toBeTruthy();
  expect(abruf).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Ihre Frage"), { target: { value: "Frage" } });
  fireEvent.click(screen.getByRole("button", { name: "Abwägen lassen" }));
  await waitFor(() => expect(screen.getByText("Das Tageskontingent ist aufgebraucht.")).toBeTruthy());
});

it("zeigt eine Absage des Servers ohne KI-Kennzeichnung einer Antwort", async () => {
  antwortet(200, { antworten: [{ text: "Diese Frage gehört nicht zur Gesundheitspolitik.", belege: [], zahlen: [], uc: "uc2", modell: null, protokoll_id: null }], fehlend: [] });
  render(<EigeneFrage />);
  fireEvent.change(screen.getByLabelText("Ihre Frage"), { target: { value: "Pizza?" } });
  fireEvent.click(screen.getByRole("button", { name: "Abwägen lassen" }));
  expect((await screen.findByTestId("uc2-eigene-absage")).textContent).toContain("nicht zur Gesundheitspolitik");
  expect(screen.queryByTestId("uc2-eigene-antwort")).toBeNull();
});

it("nimmt Werkstattwörter aus der Stimme einer Organisation und nennt die Patientenvertretung wie auf /uc2", () => {
  const g = gliedere(
    [
      "- Patient:innenvertretung: Dafür bei: „Schutz“. Grund: Wir sind dafür. Das ist eine Modellannahme, weil keine Zahl vorliegt. Das passt zur Sorge aus den Belegen. Die Patient:innenvertretung will klare Regeln. Modellannahme: Dazu gibt es keinen Zeitungsartikel. Die Haltung folgt nur aus der Beschreibung der Rolle.",
      "- Sozialversicherung: Grund: Das ist belegt.",
      "Bedingungen: Patient:innenvertretung: Klare Regeln.; Sozialversicherung: Nur mit Beleg.",
    ].join("\n"),
  );
  expect(g.stimmen[0]).toEqual({ name: "Patientenvertretung", haltung: "Dafür bei: „Schutz“.", grund: "Wir sind dafür. Die Patientenvertretung will klare Regeln.", beleg: null, ohneArtikel: true });
  expect(g.stimmen[1]?.grund).toBe("");
  expect(g.bedingungen).toEqual(["Patientenvertretung: Klare Regeln."]);
  expect(JSON.stringify(g)).not.toMatch(/Modellannahme|Beleg|innenvertretung/);
});

it("sagt Antwort und Absage in einer festen Region an, Fehler als Alarm", async () => {
  antwortet(429, { fehler: "Bitte später." });
  render(<EigeneFrage />);
  const region = screen.getByRole("status");
  expect(region.textContent).toBe("");
  fireEvent.change(screen.getByLabelText("Ihre Frage"), { target: { value: "Frage" } });
  fireEvent.click(screen.getByRole("button", { name: "Abwägen lassen" }));
  expect(region.textContent).toBe("Die Frage wird abgewogen.");
  expect((await screen.findByRole("alert")).textContent).toContain("Bitte später.");
  expect(screen.getByRole("status")).toBe(region);
});
