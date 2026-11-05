import { CACHE_MS, erstelleModellQuelle, MODELL_ARGV, type Ausfuehren } from "./modell";

// Fängt ab: ein Badge, der bei kaputtem Schalter einen geratenen Provider zeigt, ein Aufruf über eine Shell
// statt argv, und ein Subprozess je Seitenaufruf statt eines kurzen Caches.
describe("Modell-Quelle", () => {
  it("ruft uv mit festem argv in der Repo-Wurzel auf und merkt das Ergebnis 30 s", async () => {
    let uhr = 0;
    const ausfuehren = vi.fn<Ausfuehren>(async () => '{"provider": "mock", "modell": "mock", "version": null, "quelle": "env"}');
    const lese = erstelleModellQuelle({ ausfuehren, jetzt: () => uhr, wurzel: () => "/repo" });

    expect(await lese()).toEqual({ status: 200, body: { provider: "mock", modell: "mock", version: null, quelle: "env" } });
    expect(ausfuehren).toHaveBeenCalledWith("uv", MODELL_ARGV, { cwd: "/repo", timeout: 15_000 });
    uhr = CACHE_MS - 1;
    await lese();
    expect(ausfuehren).toHaveBeenCalledTimes(1);
    uhr = CACHE_MS + 1;
    await lese();
    expect(ausfuehren).toHaveBeenCalledTimes(2);
  });

  it("liefert 503 und provider unbekannt bei Fehler oder fremder Ausgabe", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    for (const ausfuehren of [
      vi.fn<Ausfuehren>(async () => {
        throw new Error("timeout");
      }),
      vi.fn<Ausfuehren>(async () => '{"provider": "mock"}'),
    ]) {
      const antwort = await erstelleModellQuelle({ ausfuehren, wurzel: () => "/repo" })();
      expect(antwort).toEqual({ status: 503, body: { provider: "unbekannt", modell: "unbekannt", version: null, quelle: "fehler" } });
    }
  });
});
