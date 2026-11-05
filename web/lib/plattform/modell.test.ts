import { CACHE_MS, erstelleModellQuelle, MODELL_ARGV, standardAusfuehren, type Ausfuehren } from "./modell";

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

  it("die echte Ausführung startet argv ohne Shell, liefert stdout und wirft bei Exit ≠ 0", async () => {
    const status = { provider: "mock", modell: "mock", version: null, quelle: "env", zuletzt: null };
    const skript = `console.log(JSON.stringify(${JSON.stringify(status)}))`;
    const stdout = await standardAusfuehren(process.execPath, ["-e", skript], { cwd: process.cwd(), timeout: 10_000 });
    expect(JSON.parse(stdout)).toEqual(status);
    // Ein Shell-Metazeichen bleibt ein Argument und wird nicht ausgewertet.
    expect(await standardAusfuehren(process.execPath, ["-e", "console.log(process.argv[1])", "$(echo x)"], { cwd: process.cwd(), timeout: 10_000 })).toBe("$(echo x)\n");
    await expect(standardAusfuehren(process.execPath, ["-e", "process.exit(3)"], { cwd: process.cwd(), timeout: 10_000 })).rejects.toThrow();
  });

  it("ruft uv mit --frozen auf, damit der Badge uv.lock nie anfasst", () => {
    expect(MODELL_ARGV.slice(0, 2)).toEqual(["run", "--frozen"]);
  });
});
