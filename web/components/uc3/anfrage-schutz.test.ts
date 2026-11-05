import { describe, expect, it } from "vitest";
import { pruefeHerkunft } from "./anfrage-schutz";

function anfrage(kopf: Record<string, string>): Request {
  return new Request("http://localhost:3218/api/uc3/freigabe", { method: "POST", headers: kopf, body: "{}" });
}

describe("pruefeHerkunft", () => {
  it("weist ein text/plain-Formular einer fremden Seite ab (CSRF ohne Vorabprüfung)", () => {
    const antwort = pruefeHerkunft(anfrage({ "content-type": "text/plain", origin: "https://boese.example" }));
    expect(antwort?.status).toBe(415);
  });

  it("weist JSON mit Sec-Fetch-Site cross-site und same-site ab", () => {
    for (const seite of ["cross-site", "same-site"]) {
      const antwort = pruefeHerkunft(anfrage({ "content-type": "application/json", "sec-fetch-site": seite }));
      expect(antwort?.status, seite).toBe(403);
    }
  });

  it("weist eine fremde Origin ab, auch wenn der Browser keine Fetch-Metadaten sendet", () => {
    const antwort = pruefeHerkunft(
      anfrage({ "content-type": "application/json", origin: "http://localhost:3000", host: "localhost:3218" }),
    );
    expect(antwort?.status).toBe(403);
  });

  it("lässt den eigenen Aufruf mit charset und den Proxy-Host der Online-Demo durch", () => {
    expect(
      pruefeHerkunft(
        anfrage({
          "content-type": "application/json; charset=utf-8",
          "sec-fetch-site": "same-origin",
          origin: "http://localhost:3218",
          host: "localhost:3218",
        }),
      ),
    ).toBeNull();
    expect(
      pruefeHerkunft(
        anfrage({
          "content-type": "application/json",
          origin: "https://demo.example",
          host: "web:3000",
          "x-forwarded-host": "demo.example",
        }),
      ),
    ).toBeNull();
  });
});
