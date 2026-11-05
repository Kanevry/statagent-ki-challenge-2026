import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { modellStatusSchema, modellUnbekannt, type ModellStatus } from "@kic/ui/shell";

// Modell-Schalter für den Badge: `uv run --frozen python -m plattform.llm status --json` als Subprozess (argv, keine
// Shell), Ergebnis 30 s im Speicher. Fehler liefern `provider: "unbekannt"` und 503, nie einen geratenen Wert.

// `--frozen`: der Badge-Aufruf ändert nie uv.lock und löst nichts neu auf.
export const MODELL_ARGV = ["run", "--frozen", "python", "-m", "plattform.llm", "status", "--json"] as const;
export const TIMEOUT_MS = 15_000;
export const CACHE_MS = 30_000;
/** Fehler kürzer merken, damit ein reparierter Schalter bald sichtbar wird, ohne bei jedem Aufruf neu zu starten. */
export const FEHLER_CACHE_MS = 5_000;

export interface ModellAntwort {
  status: 200 | 503;
  body: ModellStatus;
}

/** Läuft ein Kommando und liefert stdout; wirft bei Exit ≠ 0 oder Timeout. */
export type Ausfuehren = (befehl: string, argv: readonly string[], optionen: { cwd: string; timeout: number }) => Promise<string>;

export const standardAusfuehren: Ausfuehren = (befehl, argv, { cwd, timeout }) =>
  new Promise((aufloesen, ablehnen) => {
    execFile(befehl, [...argv], { cwd, timeout, maxBuffer: 64 * 1024, env: process.env }, (fehler, stdout) => {
      if (fehler) ablehnen(fehler);
      else aufloesen(stdout);
    });
  });

/** Repo-Wurzel: `KIC_REPO_WURZEL` oder das erste Verzeichnis ab `start` aufwärts mit `uv.lock`. */
export function findeRepoWurzel(start: string = process.cwd()): string {
  const gesetzt = process.env.KIC_REPO_WURZEL;
  if (gesetzt) return gesetzt;
  let ort = path.resolve(start);
  for (;;) {
    if (existsSync(path.join(ort, "uv.lock"))) return ort;
    const oben = path.dirname(ort);
    if (oben === ort) return path.resolve(start, "..");
    ort = oben;
  }
}

export function erstelleModellQuelle({
  ausfuehren = standardAusfuehren,
  jetzt = Date.now,
  wurzel = findeRepoWurzel,
}: { ausfuehren?: Ausfuehren; jetzt?: () => number; wurzel?: () => string } = {}) {
  let gemerkt: { bis: number; antwort: ModellAntwort } | null = null;
  let laufend: Promise<ModellAntwort> | null = null;

  async function frage(): Promise<ModellAntwort> {
    try {
      const stdout = await ausfuehren("uv", MODELL_ARGV, { cwd: wurzel(), timeout: TIMEOUT_MS });
      return { status: 200, body: modellStatusSchema.parse(JSON.parse(stdout)) };
    } catch (fehler) {
      // Nur die Art des Fehlers loggen: stderr kann Pfade oder Umgebungswerte enthalten.
      console.warn(`[plattform/modell] Modell-Schalter nicht erreichbar (${(fehler as Error).name ?? "Fehler"})`);
      return { status: 503, body: modellUnbekannt };
    }
  }

  return async function leseModell(): Promise<ModellAntwort> {
    if (gemerkt && jetzt() < gemerkt.bis) return gemerkt.antwort;
    laufend ??= frage().then((antwort) => {
      gemerkt = { bis: jetzt() + (antwort.status === 200 ? CACHE_MS : FEHLER_CACHE_MS), antwort };
      laufend = null;
      return antwort;
    });
    return laufend;
  };
}

/** Prozessweite Quelle für den Route-Handler. */
export const leseModell = erstelleModellQuelle();
