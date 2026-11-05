import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FOLIEN_ORDNER, leseFolien } from "../../lib/praesentation/folien";
import { absatzTexte } from "../../lib/praesentation/szenen-daten";
import { Schau, type SchauFolie } from "./schau";
import { szeneFuer } from "./szenen";

// Fängt ab: Pfeiltaste, die die Folie wechselt, aber die Adresse nicht mitführt (Neuladen springt zurück); Notizen,
// die ohne N sichtbar sind; Tasten, die beim Tippen in einem Feld die Folie wechseln; Wechsel über das Ende hinaus;
// ein Klick in der Folienliste, der einen Zwischenstand zeigt (Takt 0, halb gezählter Zähler) statt des Endzustands.

class Beobachter {
  observe() {}
  disconnect() {}
}

const folien: SchauFolie[] = ["Eins", "Zwei", "Drei"].map((titel, i) => ({
  id: `0${i + 1}`,
  titel,
  inhalt: <p>{`Inhalt ${titel}`}</p>,
  notizen: <p>{`Sprechtext ${titel}`}</p>,
}));

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", Beobachter);
  window.history.replaceState(null, "", "/praesentation");
});
afterEach(() => vi.unstubAllGlobals());

const aktuell = () => screen.getByRole("region", { name: /^Folie \d/ }).getAttribute("data-folie");

it("Pfeil rechts und links wechseln die Folie und schreiben ?folie=N in die Adresse, am Ende ist Schluss", async () => {
  const user = userEvent.setup();
  render(<Schau folien={folien} start={1} />);
  expect(aktuell()).toBe("1");
  await user.keyboard("{ArrowRight}");
  expect(aktuell()).toBe("2");
  expect(window.location.search).toBe("?folie=2");
  await user.keyboard("{ArrowRight}{ArrowRight}");
  expect(aktuell()).toBe("3");
  expect(window.location.search).toBe("?folie=3");
  await user.keyboard("{ArrowLeft}");
  expect(window.location.search).toBe("?folie=2");
});

it("startet auf der übergebenen Folie und die Knöpfe sind am Rand gesperrt", () => {
  render(<Schau folien={folien} start={3} />);
  expect(aktuell()).toBe("3");
  expect((screen.getByRole("button", { name: "Nächste Folie" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Vorherige Folie" }) as HTMLButtonElement).disabled).toBe(false);
});

it("Notizen sind erst nach N sichtbar und nach erneutem N wieder weg", async () => {
  const user = userEvent.setup();
  render(<Schau folien={folien} start={1} />);
  expect(screen.queryByText("Sprechtext Eins")).toBeNull();
  await user.keyboard("n");
  expect(screen.getByText("Sprechtext Eins")).toBeTruthy();
  await user.keyboard("N");
  expect(screen.queryByText("Sprechtext Eins")).toBeNull();
});

it("Tasten in einem Eingabefeld wechseln die Folie nicht", async () => {
  const user = userEvent.setup();
  render(
    <>
      <input aria-label="Feld" />
      <Schau folien={folien} start={1} />
    </>,
  );
  await user.click(screen.getByLabelText("Feld"));
  await user.keyboard("n{ArrowRight}");
  expect(aktuell()).toBe("1");
  expect(screen.queryByText("Sprechtext Eins")).toBeNull();
});

describe("Sprung aus der Folienliste", () => {
  const echte: SchauFolie[] = leseFolien(FOLIEN_ORDNER).map((f) => ({
    id: f.id,
    titel: f.titel,
    inhalt: null,
    notizen: null,
    ...(f.szene ? { szene: { id: f.szene, folie: f } } : {}),
  }));
  const takteVon = (i: number) => szeneFuer(echte[i]?.szene?.id)?.takte ?? 0;
  const region = () => screen.getByRole("region", { name: /^Folie \d/ });
  const listenKnopf = (nr: number) => within(screen.getByRole("navigation", { name: "Folien" })).getAllByRole("button")[nr - 1]!;
  const aktiveSzene = (c: HTMLElement) => c.querySelector<HTMLElement>('[data-aktiv="ja"]')!;

  it("öffnet jede Szene im Endzustand mit allen Takten und still; Tasten schalten danach wie gewohnt", async () => {
    const user = userEvent.setup();
    const { container } = render(<Schau folien={echte} start={1} />);
    const mitTakten = echte.map((_, i) => i).filter((i) => takteVon(i) > 0);
    expect(mitTakten.length).toBeGreaterThan(0);
    for (const i of mitTakten) {
      await user.click(listenKnopf(i + 1));
      expect(region().getAttribute("data-folie")).toBe(String(i + 1));
      expect(region().getAttribute("data-takt"), echte[i]!.id).toBe(String(takteVon(i)));
      expect(aktiveSzene(container).dataset.still, echte[i]!.id).toBe("ja");
      // Jedes Takt-Element ist angeschaltet, nichts wartet auf einen weiteren Tastendruck.
      for (const e of aktiveSzene(container).querySelectorAll<HTMLElement>("[data-takt]")) {
        expect((e.getAttribute("class") ?? "").split(" ").some((c) => c === "an" || /(^|_)an(_|$)/.test(c))).toBe(true);
      }
    }
    // Zurück innerhalb der stillen Szene bleibt still, erst der Folienwechsel per Taste läuft wieder animiert.
    const letzte = mitTakten.at(-1)!;
    await user.keyboard("{ArrowLeft}");
    expect(region().getAttribute("data-takt")).toBe(String(takteVon(letzte) - 1));
    expect(aktiveSzene(container).dataset.still).toBe("ja");
    await user.keyboard("{ArrowRight}{ArrowRight}");
    expect(region().getAttribute("data-folie")).toBe(String(letzte + 2));
    expect(region().getAttribute("data-takt")).toBe("0");
    expect(aktiveSzene(container).dataset.still).toBeUndefined();
  });

  it("zeigt den Zähler der Szene beleg sofort mit dem Endwert", async () => {
    const user = userEvent.setup();
    const { container } = render(<Schau folien={echte} start={1} />);
    const i = echte.findIndex((f) => f.szene?.id === "beleg");
    expect(i).toBeGreaterThanOrEqual(0);
    await user.click(listenKnopf(i + 1));
    // Ein laufender Zähler stünde nach 100 ms noch bei 0 (er beginnt erst nach 1,2 s).
    await act(() => new Promise((fertig) => setTimeout(fertig, 100)));
    const zahl = aktiveSzene(container).querySelector('[class*="s5-zahl"]');
    // Endwert wie in beleg.tsx: die Zahl am Anfang des ersten Absatzes.
    const ziel = /^[\d.]+/.exec(absatzTexte(echte[i]!.szene!.folie)[0] ?? "")?.[0];
    expect(ziel).toBeTruthy();
    expect(zahl?.textContent).toBe(ziel);
  });
});
