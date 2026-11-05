import { execFile } from "node:child_process";
// Relativ statt "@/…": vitest.config.ts (E0) kennt den Alias nicht, so bleibt die Datei in Tests ladbar.
import { findeRepoWurzel } from "../../lib/plattform/modell";

/**
 * Aufruf der UC3-CLI (`uv run --frozen --package statagent uc3 …`) als Subprozess mit argv, nie über eine Shell. Nur für Schreibwege
 * (Freigabe, Ablehnung) und Fragen; Lesen geht direkt an die Datenbank (`db.ts`). web/ ruft nie ein Modell.
 *
 * `UC3_CLI_WURZEL` lenkt den Aufruf auf einen anderen Checkout, in dem `uc3/` liegt (Entwicklung, solange uc3/ nicht
 * auf main ist); ohne Angabe die Repo-Wurzel dieses Checkouts.
 */

// `--package statagent`: uv installiert das Workspace-Mitglied uc3/ bei Bedarf; ohne den Schalter fehlt das
// Programm `uc3`, wenn nur `uv sync` ohne `--all-packages` lief (gemessen 05.11.).
export const UC3_ARGV = ["run", "--frozen", "--package", "statagent", "uc3"] as const;
export const TIMEOUT_MS = 120_000;
export const MAX_BUFFER = 2 * 1024 * 1024;

export interface CliLauf {
  code: number;
  stdout: string;
  stderr: string;
}

export type Ausfuehren = (
  befehl: string,
  argv: readonly string[],
  optionen: { cwd: string; timeout: number; maxBuffer: number },
) => Promise<CliLauf>;

export const standardAusfuehren: Ausfuehren = (befehl, argv, { cwd, timeout, maxBuffer }) =>
  new Promise((aufloesen, ablehnen) => {
    execFile(befehl, [...argv], { cwd, timeout, maxBuffer, env: process.env }, (fehler, stdout, stderr) => {
      if (!fehler) aufloesen({ code: 0, stdout, stderr });
      // Regulärer Exit ≠ 0 ist ein Ergebnis (z. B. „Name ungültig“); Timeout, Abbruch und Startfehler werfen.
      else if (typeof fehler.code === "number" && !fehler.killed) aufloesen({ code: fehler.code, stdout, stderr });
      else ablehnen(fehler);
    });
  });

export function cliWurzel(umgebung: Readonly<Record<string, string | undefined>> = process.env): string {
  return umgebung.UC3_CLI_WURZEL?.trim() || findeRepoWurzel();
}

export interface Uc3Optionen {
  ausfuehren?: Ausfuehren;
  wurzel?: () => string;
  timeout?: number;
}

/** Ruft `uc3 <argv…>` auf; `argv` sind die Argumente nach dem Programmnamen. */
export function uc3(argv: readonly string[], optionen: Uc3Optionen = {}): Promise<CliLauf> {
  const { ausfuehren = standardAusfuehren, wurzel = () => cliWurzel(), timeout = TIMEOUT_MS } = optionen;
  return ausfuehren("uv", [...UC3_ARGV, ...argv], { cwd: wurzel(), timeout, maxBuffer: MAX_BUFFER });
}

/** Online-Demo: alles bleibt lesend, Schreibwege antworten 403 (gleiche Sperre wie /api/uc4/frage). */
export function nurLesend(umgebung: Readonly<Record<string, string | undefined>> = process.env): boolean {
  return umgebung.KIC_ONLINE_LESEND === "1";
}
