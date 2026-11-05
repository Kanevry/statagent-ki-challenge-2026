import type { ComponentType } from "react";
import { Annahme } from "./annahme";
import { BelegSzene } from "./beleg";
import { DreiFragen } from "./drei-fragen";
import { Einstieg } from "./einstieg";
import { Fehler } from "./fehler";
import { FalscheZahl } from "./falsche-zahl";
import type { SzeneProps } from "./gemeinsam";
import { Gleichung } from "./gleichung";
import { Kern } from "./kern";
import { Schluss } from "./schluss";
import { Woerterbuecher } from "./woerterbuecher";
import { ZahlenSzene } from "./zahlen";

export type { SzeneProps } from "./gemeinsam";

/** Eine Szene: Komponente und Zahl ihrer Takte (Tastendrücke innerhalb der Szene, 0 = keine). */
export interface SzenenEintrag {
  Komponente: ComponentType<SzeneProps>;
  takte: number;
}

/**
 * Registry `szene` (Frontmatter) zu Komponente, Szenenfolge v4 „1 + 2 + 3 = 4“ mit zehn Szenen (#59, Lane E5).
 * Takte (je ein Klick, ein Satz, eine Bewegung) in falsche-zahl, kern, beleg, fehler, annahme und einstieg.
 * Nur was hier steht, wird als Szene gezeigt; eine unbekannte oder fehlende `szene` fällt auf `layout` zurück.
 */
export const SZENEN: Readonly<Record<string, SzenenEintrag>> = {
  gleichung: { Komponente: Gleichung, takte: 0 },
  "drei-fragen": { Komponente: DreiFragen, takte: 0 },
  "falsche-zahl": { Komponente: FalscheZahl, takte: 3 },
  kern: { Komponente: Kern, takte: 3 },
  beleg: { Komponente: BelegSzene, takte: 1 },
  fehler: { Komponente: Fehler, takte: 3 },
  woerterbuecher: { Komponente: Woerterbuecher, takte: 0 },
  annahme: { Komponente: Annahme, takte: 3 },
  einstieg: { Komponente: Einstieg, takte: 3 },
  schluss: { Komponente: Schluss, takte: 0 },
  zahlen: { Komponente: ZahlenSzene, takte: 0 },
};

/** Eintrag zu einer Szene, oder `undefined` für unbekannt und leer. */
export function szeneFuer(id: string | undefined): SzenenEintrag | undefined {
  return id !== undefined && Object.hasOwn(SZENEN, id) ? SZENEN[id] : undefined;
}
