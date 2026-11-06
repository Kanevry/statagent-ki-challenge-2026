import { renderToStaticMarkup } from "react-dom/server";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import Datenfehler from "./Datenfehler";

// Fehler: Der Stand ging auf dem Server, der in UTC läuft, eine Stunde nach. Deshalb hier fest UTC, auch am Mac.
const tzVorher = process.env.TZ;
beforeAll(() => {
  process.env.TZ = "UTC";
});
afterAll(() => {
  process.env.TZ = tzVorher;
});

function seite(stand: string): string {
  return renderToStaticMarkup(<Datenfehler tabelle={{ quelle: "datenbank", zeilen: [], anzahl: 0, stand }} />);
}

describe("Stand der Tabelle", () => {
  it("zeigt Wiener Zeit, im Winter UTC plus eine Stunde", () => {
    expect(seite("2026-11-06T05:25:00.000Z")).toContain("Stand 06.11.2026, 06:25");
  });

  it("zeigt Wiener Zeit, im Sommer UTC plus zwei Stunden", () => {
    expect(seite("2026-07-01T10:00:00.000Z")).toContain("Stand 01.07.2026, 12:00");
  });
});
