import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FreigabeKarte, formatZeit, type FreigabeKarteProps } from "../../src/bausteine";

const eintrag = {
  anweisung: "Prüfregel P07 ab 2025-01 als Fehler statt Warnung führen",
  name: "Anna Beispiel",
  zeit: "2026-11-05T09:12:30+00:00",
};

function karte(props: Partial<FreigabeKarteProps> = {}) {
  const onFreigeben = vi.fn<FreigabeKarteProps["onFreigeben"]>();
  const onAblehnen = vi.fn<FreigabeKarteProps["onAblehnen"]>();
  render(
    <FreigabeKarte
      eintrag={eintrag}
      vorher={387390}
      nachher={387130}
      onFreigeben={onFreigeben}
      onAblehnen={onAblehnen}
      {...props}
    />,
  );
  const knopf = screen.getByRole("button", { name: "Freigeben" }) as HTMLButtonElement;
  const feld = screen.getByRole("textbox", { name: "Vor- und Nachname" });
  return { onFreigeben, onAblehnen, knopf, feld };
}

// Fängt ab: falsches Vorzeichen (Bindestrich statt U+2212), Tausendertrennung per Leerzeichen
// (ICU-Standard für de-AT) und eine Prozentzahl mit falscher Basis.
it("zeigt vorher, nachher, Δ −260 und −0,07 % im Format de-AT", () => {
  karte();
  const waage = screen.getByLabelText("Freigabe-Waage");
  expect(waage.textContent).toContain("387.390");
  expect(waage.textContent).toContain("387.130");
  expect(screen.getByText("−260")).toBeTruthy();
  expect(screen.getByText("−0,07 %")).toBeTruthy();
});

// Fängt ab: Bausteine der Karte, die beim Umbau ihre Reihenfolge tauschen (Freigabe vor dem Zitat) oder die
// Überschrift verlieren, nach der die Karte benannt ist.
it("hält die Reihenfolge Titel, Zitat, Diff, Waage, Beleg, Freigabe und benennt die Karte nach dem Titel", () => {
  karte({ diff: "-a\n+b", beleg: { lieferung: "2025-03" } });
  expect(screen.getAllByRole("heading").map((h) => h.textContent)).toEqual(["Vorschlag des Agenten"]);
  expect(screen.getByRole("article", { name: "Vorschlag des Agenten" })).toBeTruthy();
  const reihe = ["Vorschlag des Agenten", "„Prüfregel P07", "-a", "Bestand vorher", "roh.lieferung", "Freigeben"];
  const text = document.body.textContent ?? "";
  const stellen = reihe.map((teil) => text.indexOf(teil));
  expect(stellen.every((stelle) => stelle >= 0), String(stellen)).toBe(true);
  expect([...stellen].sort((x, y) => x - y)).toEqual(stellen);
});

// Fängt ab: ein Modell, das nur in den Details steht, statt wie im Frame FgY98 als Pille im Kopf.
it("zeigt das Modell als Pille im Kopf, mit Punkt und dem Wort austauschbar", () => {
  karte({ eintrag: { ...eintrag, modell: "azure · gpt-5-4-mini" } });
  const pille = document.querySelector('[data-baustein="modell"]');
  expect(pille?.textContent).toBe("Modell:azure · gpt-5-4-mini· austauschbar");
  expect(pille?.className).toContain("bg-violett-bg");
  expect(pille?.querySelector('[aria-hidden="true"]')).not.toBeNull();
});

// Fängt ab: ein Diff, der erst nach dem Aufklappen sichtbar wird (Frame FgY98 zeigt ihn offen), und Farbe als
// einziger Unterschied zwischen entfernt und neu (das Zeichen vor der Zeile muss bleiben).
it("zeigt den Diff offen, entfernt in Rot und neu in Grün, mit Vorzeichen im Text", () => {
  karte({ diff: "-regel: aus\n+regel: an" });
  const aus = screen.getByText("-regel: aus");
  const an = screen.getByText("+regel: an");
  expect(aus.className).toContain("text-err-fg");
  expect(an.className).toContain("text-gruen");
  expect(aus.closest("details")).toBeNull();
});

// Fängt ab: Freigabe durch eine Rolle oder einen Vornamen allein, entgegen Vertrag P.
it("aktiviert den Knopf erst bei gültigem Vor- und Nachnamen", async () => {
  const user = userEvent.setup();
  const { knopf, feld } = karte();
  expect(knopf.disabled).toBe(true);
  for (const name of ["Team", "Bernhard"]) {
    await user.clear(feld);
    await user.type(feld, name);
    expect(knopf.disabled, name).toBe(true);
  }
  await user.clear(feld);
  await user.type(feld, "Bernhard Götzendorfer");
  expect(knopf.disabled).toBe(false);
});

// Fängt ab: Enter im Namensfeld gibt frei, direkt oder über ein umgebendes Formular.
it("löst mit Enter im Namensfeld nichts aus", async () => {
  const user = userEvent.setup();
  const senden = vi.fn((e: { preventDefault: () => void }) => e.preventDefault());
  const onFreigeben = vi.fn();
  render(
    <form onSubmit={senden}>
      <FreigabeKarte eintrag={eintrag} vorher={387390} nachher={387130} onFreigeben={onFreigeben} onAblehnen={vi.fn()} />
    </form>,
  );
  await user.type(screen.getByRole("textbox", { name: "Vor- und Nachname" }), "Bernhard Götzendorfer{Enter}");
  expect(onFreigeben).not.toHaveBeenCalled();
  expect(senden).not.toHaveBeenCalled();
});

// Fängt ab: Leerzeichen am Rand landen im Freigabe-Namen (und damit im Commit-Trailer).
it("ruft onFreigeben beim Klick mit dem getrimmten Namen", async () => {
  const user = userEvent.setup();
  const { onFreigeben, knopf, feld } = karte();
  await user.type(feld, "  Bernhard Götzendorfer  ");
  await user.click(knopf);
  expect(onFreigeben).toHaveBeenCalledTimes(1);
  expect(onFreigeben).toHaveBeenCalledWith("Bernhard Götzendorfer");
  expect((await screen.findByText(/Freigegeben von Bernhard Götzendorfer/)).textContent).toBeTruthy();
});

// Fängt ab: eine im Server abgelehnte Freigabe erscheint trotzdem als freigegeben.
it("zeigt einen Fehler und bleibt offen, wenn der Server ablehnt", async () => {
  const user = userEvent.setup();
  const { knopf, feld } = karte({ onFreigeben: () => Promise.reject(new Error("Name abgelehnt.")) });
  await user.type(feld, "Bernhard Götzendorfer");
  await user.click(knopf);
  expect((await screen.findByRole("alert")).textContent).toContain("Name abgelehnt.");
  expect(screen.queryByText(/Freigegeben von/)).toBeNull();
  expect(knopf.disabled).toBe(false);
});

// Fängt ab: eine Live-Region, die erst mit dem Ergebnis entsteht (Screenreader melden sie oft nicht),
// und ein Fokus, der mit dem verschwundenen Knopf im Nichts landet.
it("setzt das Ergebnis in die schon vorhandene Live-Region und fokussiert sie", async () => {
  const user = userEvent.setup();
  const { knopf, feld } = karte();
  const region = document.querySelector('[data-meldung="freigabe"]');
  expect(region?.getAttribute("aria-live")).toBe("polite");
  expect(region?.textContent).toBe("");
  await user.type(feld, "Bernhard Götzendorfer");
  await user.click(knopf);
  await screen.findByText(/Freigegeben von Bernhard Götzendorfer/);
  expect(document.querySelector('[data-meldung="freigabe"]')).toBe(region);
  expect(region?.textContent).toContain("Freigegeben von Bernhard Götzendorfer");
  expect(document.activeElement).toBe(region);
});

// Fängt ab: Ablehnung ohne Begründung, oder eine Begründung, die nicht beim Aufrufer ankommt.
it("verlangt beim Ablehnen eine Begründung und übergibt Name und Begründung", async () => {
  const user = userEvent.setup();
  const { onAblehnen, feld } = karte();
  await user.type(feld, "Bernhard Götzendorfer");
  await user.click(screen.getByRole("button", { name: "Ablehnen" }));
  const speichern = screen.getByRole("button", { name: "Ablehnung speichern" }) as HTMLButtonElement;
  expect(speichern.disabled).toBe(true);
  await user.type(screen.getByRole("textbox", { name: "Begründung der Ablehnung" }), "  Erst 2025-04 prüfen ");
  expect(speichern.disabled).toBe(false);
  await user.click(speichern);
  expect(onAblehnen).toHaveBeenCalledTimes(1);
  expect(onAblehnen).toHaveBeenCalledWith("Bernhard Götzendorfer", "Erst 2025-04 prüfen");
});

// Fängt ab: Doppelklick während der Server noch antwortet erzeugt zwei Freigaben.
it("hält den Knopf gesperrt, solange die Freigabe läuft", async () => {
  const user = userEvent.setup();
  const onFreigeben = vi.fn(() => new Promise<void>(() => {}));
  const { knopf, feld } = karte({ onFreigeben });
  await user.type(feld, "Bernhard Götzendorfer");
  await user.click(knopf);
  expect(knopf.disabled).toBe(true);
  await user.click(knopf);
  expect(onFreigeben).toHaveBeenCalledTimes(1);
  expect(screen.getByText("Wird gespeichert")).toBeTruthy();
});

// Fängt ab: die Karte zeigt die Uhr des Browsers statt des Zeitpunkts aus meta.freigabe.
it("zeigt den Zeitpunkt, den der Server zurückgibt", async () => {
  const user = userEvent.setup();
  const zeitpunkt = "2020-01-02T03:04:00+00:00";
  const { knopf, feld } = karte({ onFreigeben: () => Promise.resolve({ zeitpunkt }) });
  await user.type(feld, "Bernhard Götzendorfer");
  await user.click(knopf);
  expect(await screen.findByText(`Freigegeben von Bernhard Götzendorfer, ${formatZeit(zeitpunkt)}`)).toBeTruthy();
});

// Fängt ab: Anleitung nur im Platzhalter (verschwindet beim Tippen) und ein gesperrter Knopf ohne Grund, bis
// das Feld verlassen wird.
it("hat ein sichtbares Label, einen dauerhaften Hinweis und nennt den Sperrgrund schon beim Tippen", async () => {
  const user = userEvent.setup();
  const { feld, knopf } = karte();
  const label = document.querySelector(`label[for="${feld.id}"]`);
  expect(label?.textContent).toBe("Vor- und Nachname");
  expect(feld.getAttribute("placeholder")).toBeNull();
  const hinweis = document.getElementById(feld.getAttribute("aria-describedby")!.split(" ")[0]!);
  expect(hinweis?.textContent).toContain("wird mit der Änderung gespeichert");
  await user.type(feld, "Bernhard");
  expect(document.activeElement).toBe(feld);
  expect(knopf.disabled).toBe(true);
  expect(screen.getByText("Bitte Vor- und Nachname eingeben.")).toBeTruthy();
  expect(feld.getAttribute("aria-describedby")?.split(" ")).toHaveLength(2);
  expect(hinweis?.isConnected).toBe(true);
});

// Fängt ab: Fachwörter in der Karte, die ohne Vorwissen niemand versteht (Commit, Diff, Δ).
it("spricht ohne Commit, Diff und Δ", () => {
  karte({ eintrag: { ...eintrag, ref: "regel:P07@2" } });
  const text = document.body.textContent ?? "";
  expect(text).not.toMatch(/Commit|Diff|Δ/);
  expect(text).toContain("Keine Regeländerung hinterlegt.");
  expect(screen.getByText("Unterschied")).toBeTruthy();
});

// Fängt ab: der geklickte Knopf verschwindet und der Fokus fällt auf body.
it("setzt den Fokus nach „Ablehnen“ ins Begründungsfeld und nach „Zurück“ wieder auf „Ablehnen“", async () => {
  const user = userEvent.setup();
  karte();
  await user.click(screen.getByRole("button", { name: "Ablehnen" }));
  expect(document.activeElement).toBe(screen.getByRole("textbox", { name: "Begründung der Ablehnung" }));
  await user.click(screen.getByRole("button", { name: "Zurück" }));
  expect(document.activeElement).toBe(screen.getByRole("button", { name: "Ablehnen" }));
});
