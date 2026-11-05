import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { FOLIEN_ORDNER, istInterneRoute, LAYOUTS, leseFolien, parseFolie, zeitStart, zeitText } from "./folien";
import { inlineText } from "./markdown";
import { LIVE_ROUTEN } from "./live";

// Fängt ab: Sprechtext, der auf der Folie landet; ein unbekanntes Layout, das die Folie leer lässt; eine Route aus
// dem Markdown, die nicht in der Registry steht; Reihenfolge nach Text statt Zahl (10 vor 2); die README als Folie;
// ein Tippfehler in einer echten Folie (Layout, fehlende oder nicht freigegebene live-Route).

const MIT_ALLEM = `---
titel: "Mein Titel"
layout: live
route: /uc3
zeit: "3:15–4:15"
nummer: 3
bereiche: [alle]
screenshot: null
---

# Mein Titel

Text auf der Folie.

<!-- notizen -->

Nur zum Sprechen.
`;

describe("parseFolie", () => {
  it("trennt Folie und Sprechtext an der Notiz-Zeile", () => {
    const f = parseFolie("03-x.md", MIT_ALLEM);
    expect(f.inhalt.map((b) => b.art)).toEqual(["ueberschrift", "absatz"]);
    expect(JSON.stringify(f.inhalt)).not.toContain("Nur zum Sprechen");
    expect(f.notizen.map((b) => (b.art === "absatz" ? inlineText(b.inline) : ""))).toEqual(["Nur zum Sprechen."]);
  });

  it("liest Frontmatter mit Anführungszeichen, ignoriert Listen und null", () => {
    const f = parseFolie("03-x.md", MIT_ALLEM);
    expect(f).toMatchObject({ id: "03-x", titel: "Mein Titel", layout: "live", route: "/uc3", zeit: "3:15–4:15" });
    expect(f.zahl).toBeUndefined();
  });

  it("liest szene klein geschrieben und behält alle Frontmatter-Werte in daten", () => {
    const f = parseFolie("02-x.md", "---\ntitel: A\nlayout: text\nszene: Falsche-Zahl\nzahl_geliefert: 313.154\nscreenshot: null\n---\n# A");
    expect(f.szene).toBe("falsche-zahl");
    expect(f.daten).toMatchObject({ titel: "A", layout: "text", zahl_geliefert: "313.154" });
    expect(f.daten).not.toHaveProperty("screenshot");
    expect(parseFolie("a.md", "# A").szene).toBeUndefined();
  });

  it("nimmt auch die Überschrift „Sprechernotizen“ als Trenner", () => {
    const f = parseFolie("a.md", "# A\n\ntext\n\n## Sprechernotizen\n\nleise\n");
    expect(f.inhalt).toHaveLength(2);
    expect(f.notizen).toHaveLength(1);
  });

  it("macht aus einem unbekannten oder fehlenden Layout `text`, aus cover `titel`", () => {
    expect(parseFolie("a.md", "---\ntitel: A\nlayout: diagramm\n---\n# A").layout).toBe("text");
    expect(parseFolie("a.md", "---\ntitel: A\n---\n# A").layout).toBe("text");
    expect(parseFolie("a.md", "---\ntitel: A\nlayout: cover\n---\n# A").layout).toBe("titel");
  });

  it("behält route nur bei live", () => {
    expect(parseFolie("a.md", "---\ntitel: A\nlayout: text\nroute: /uc3\n---\n# A").route).toBeUndefined();
  });

  it("kommt ohne Frontmatter aus: Titel aus der ersten Überschrift, sonst aus dem Dateinamen", () => {
    expect(parseFolie("01-x.md", "# Erste\n\ntext").titel).toBe("Erste");
    expect(parseFolie("02-nur-text.md", "nur Text").titel).toBe("nur-text");
  });

  it("verträgt Windows-Zeilenenden", () => {
    const f = parseFolie("a.md", "---\r\ntitel: A\r\nlayout: zahl\r\n---\r\n# A\r\n\r\n<!-- notizen -->\r\nleise");
    expect(f.layout).toBe("zahl");
    expect(f.notizen).toHaveLength(1);
  });
});

describe("istInterneRoute", () => {
  it.each(["/uc3", "/uc3/lauf", "/"])("lässt %s zu", (r) => expect(istInterneRoute(r)).toBe(true));
  it.each(["//evil.example", "https://evil.example", "javascript:alert(1)", "uc3", "", undefined])("lehnt %j ab", (r) =>
    expect(istInterneRoute(r)).toBe(false),
  );
});

describe("Zeitangaben", () => {
  it("nimmt den Anfang und schreibt Bereiche ohne Strich", () => {
    expect(zeitStart("3:15–4:15")).toBe("3:15");
    expect(zeitText("3:15–4:15")).toBe("3:15 bis 4:15");
    expect(zeitStart("0:00")).toBe("0:00");
    expect(zeitStart(undefined)).toBeUndefined();
  });
});

describe("leseFolien", () => {
  let ordner: string;
  beforeEach(() => {
    ordner = mkdtempSync(path.join(tmpdir(), "folien-"));
  });
  afterEach(() => rmSync(ordner, { recursive: true, force: true }));

  it("sortiert nach Dateiname mit Zahlen als Zahlen und überspringt README und fremde Dateien", () => {
    for (const n of ["10-zehn.md", "2-zwei.md", "01-eins.md", "README.md", "notiz.txt"]) writeFileSync(path.join(ordner, n), `# ${n}`);
    expect(leseFolien(ordner).map((f) => f.id)).toEqual(["01-eins", "2-zwei", "10-zehn"]);
  });

  it("liefert eine leere Liste, wenn der Ordner fehlt", () => {
    expect(leseFolien(path.join(ordner, "gibt-es-nicht"))).toEqual([]);
  });
});

describe("echte Folien in web/content/slides", () => {
  const folien = leseFolien(FOLIEN_ORDNER);

  it("es gibt mindestens eine Folie", () => {
    expect(folien.length).toBeGreaterThan(0);
  });

  it.each(folien.map((f) => [f.id, f] as const))("%s: Titel da, Layout bekannt, live-Route freigegeben", (_id, f) => {
    expect(f.titel).not.toBe("");
    expect(LAYOUTS).toContain(f.layout);
    if (f.layout === "live") {
      expect(f.route, "live braucht route").toBeDefined();
      expect(Object.keys(LIVE_ROUTEN), "Route steht nicht in web/lib/praesentation/live.tsx").toContain(f.route);
    }
  });
});
