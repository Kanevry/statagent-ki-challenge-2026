import type { ComponentType } from "react";
import { Annahme } from "./annahme";
import { BelegSzene } from "./beleg";
import { DreiFragen } from "./drei-fragen";
import { Einstieg } from "./einstieg";
import { Fallen } from "./fallen";
import { FalscheZahl, TAKTE_FALSCHE_ZAHL } from "./falsche-zahl";
import type { SzeneProps } from "./gemeinsam";
import { Gleichung } from "./gleichung";
import { Kern } from "./kern";
import { Schluss } from "./schluss";

export type { SzeneProps } from "./gemeinsam";

/** Eine Szene: Komponente und Zahl ihrer Takte (Tastendrücke innerhalb der Szene, 0 = keine). */
export interface SzenenEintrag {
  Komponente: ComponentType<SzeneProps>;
  takte: number;
}

/**
 * Registry `szene` (Frontmatter) zu Komponente, Szenenfolge v3 „1 + 2 + 3 = 4“ (#59, Lane E5). Nur was hier steht,
 * wird als Szene gezeigt; eine unbekannte oder fehlende `szene` fällt auf das Layout aus `layout` zurück.
 */
export const SZENEN: Readonly<Record<string, SzenenEintrag>> = {
  gleichung: { Komponente: Gleichung, takte: 0 },
  "drei-fragen": { Komponente: DreiFragen, takte: 0 },
  "falsche-zahl": { Komponente: FalscheZahl, takte: TAKTE_FALSCHE_ZAHL },
  kern: { Komponente: Kern, takte: 0 },
  beleg: { Komponente: BelegSzene, takte: 0 },
  fallen: { Komponente: Fallen, takte: 0 },
  annahme: { Komponente: Annahme, takte: 0 },
  einstieg: { Komponente: Einstieg, takte: 0 },
  schluss: { Komponente: Schluss, takte: 0 },
};

/** Eintrag zu einer Szene, oder `undefined` für unbekannt und leer. */
export function szeneFuer(id: string | undefined): SzenenEintrag | undefined {
  return id !== undefined && Object.hasOwn(SZENEN, id) ? SZENEN[id] : undefined;
}
