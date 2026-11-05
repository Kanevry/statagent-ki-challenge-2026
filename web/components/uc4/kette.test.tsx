import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { UcAntwort } from "@kic/ui/antwortform";
import { Kette } from "./kette";

const BELEG_UC3 = { uc: "uc3", quelle: "stat.stat_beschaeftigte", lieferung: "2025-03", monat: "2025-03", regelstand: "v1", sql: "select 1", lauf: null, ref: null, stand: "endgueltig" };
const PRESSE = { ...BELEG_UC3, uc: "uc2", quelle: "presse: Kurier", sql: null, regelstand: null, lieferung: null, ref: "b1", stand: null };
const EXPERTE = { ...PRESSE, quelle: "uc2.experte", ref: "paket" };
const ZAHL = { bezeichnung: "Beschäftigungsverhältnisse", wert: 7498, einheit: "Anzahl", beleg: 0 };

function antwort(uc: string, text: string, belege: unknown[], zahlen: unknown[]): UcAntwort {
  return { uc, text, belege, zahlen, modell: uc === "uc3" ? null : "gpt-5-4-mini", protokoll_id: null } as unknown as UcAntwort;
}

const UC3 = antwort("uc3", "Am 31.03.2025 gab es 7.498 Beschäftigungsverhältnisse.", [BELEG_UC3], [ZAHL]);
const UC2 = antwort(
  "uc2",
  "Mehr Personal heißt meist kürzere Wartezeiten. Weniger Personal heißt meist längere Wartezeiten.\nDie Zahl aus der Statistik: 7.498.\nWer ist dafür, wer dagegen:",
  [BELEG_UC3, EXPERTE, PRESSE, PRESSE],
  [ZAHL],
);
const UC1 = antwort("uc1", "Für Ihren nächsten Arzttermin heißt das: Sie warten oft kürzer. Die Zahl dahinter für März 2025: 7.498 Beschäftigungsverhältnisse.", [BELEG_UC3, PRESSE], [ZAHL]);

function strom(...antworten: UcAntwort[]): Response {
  const zeilen: unknown[] = [{ art: "start", kette: ["uc3", "uc2", "uc1"], modell: null }];
  antworten.forEach((a, i) => {
    zeilen.push({ art: "station", uc: a.uc, stufe: i + 1, zustand: "laeuft" });
    zeilen.push({ art: "antwort", uc: a.uc, stufe: i + 1, dauer_ms: 900, kern: a.text.split(". ")[0], antwort: a });
  });
  zeilen.push({ art: "ende", fehlend: [], dauer_ms: 1000 });
  return new Response(zeilen.map((z) => JSON.stringify(z)).join("\n") + "\n", { status: 200 });
}

async function fragen(antwort: Response) {
  vi.stubGlobal("fetch", vi.fn(async (ziel: string) => (String(ziel).includes("uc4/frage") ? antwort : new Response("{}", { status: 200 }))));
  const { container } = render(<Kette kette={["uc3", "uc2", "uc1"]} fragenOffen mitModell={false} />);
  const nutzer = userEvent.setup();
  await nutzer.type(screen.getByLabelText("Ihre Frage"), "Wie viele?{Enter}");
  await waitFor(() => expect(container.querySelector('[data-zustand="laeuft"]')).toBeNull());
  return container;
}

afterEach(() => vi.unstubAllGlobals());

it("die Zahl steht mit ihren Angaben nur bei Station 1, nicht dreimal (#164)", async () => {
  const seite = await fragen(strom(UC3, UC2, UC1));
  await screen.findByText(/Fertig in/);
  expect(seite.querySelectorAll("[data-zahl]")).toHaveLength(1);
  expect(seite.querySelector('[data-uc-karte="uc3"] [data-zahl]')).not.toBeNull();
});

it("der Simulator zeigt oben seine Aussage und seine eigenen Quellen, nicht die Zahl von StatAgent", async () => {
  const seite = await fragen(strom(UC3, UC2, UC1));
  await screen.findByText(/Fertig in/);
  const karte = seite.querySelector('[data-uc-karte="uc2"]')!;
  const aussage = karte.querySelector("[data-uc4-antwort] p")!.textContent;
  expect(aussage).toBe("Mehr Personal heißt meist kürzere Wartezeiten. Weniger Personal heißt meist längere Wartezeiten.");
  // Zwei gleiche Quellen zählen einmal, Rechenmodell und weitergereichte Zahl fehlen hier.
  expect(karte.querySelectorAll('[data-baustein="herkunft"]')).toHaveLength(1);
  expect(karte.querySelector('[data-baustein="herkunft"]')!.textContent).toContain("presse: Kurier");
});

it("der Lotse zeigt den Beleg seiner Zahl", async () => {
  const seite = await fragen(strom(UC3, UC2, UC1));
  await screen.findByText(/Fertig in/);
  const karte = seite.querySelector('[data-uc-karte="uc1"]')!;
  expect(karte.querySelector("[data-uc4-antwort] p")!.textContent).toContain("Arzttermin");
  expect(karte.querySelector('[data-baustein="herkunft"]')!.textContent).toContain("stat.stat_beschaeftigte");
});

it("ohne Zahl von Station 1 steht nur deren Rückfrage da, ohne leere Stationen", async () => {
  const seite = await fragen(strom(antwort("uc3", "Bitte nennen Sie einen Monat, zum Beispiel März 2025.", [], [])));
  await waitFor(() => expect(seite.querySelectorAll("[data-uc-karte]")).toHaveLength(1));
  expect(seite.querySelector("[data-uc-karte]")!.getAttribute("data-uc-karte")).toBe("uc3");
  expect(seite.textContent).toContain("Bitte nennen Sie einen Monat");
  expect(seite.textContent).not.toContain("Fertig in");
});
