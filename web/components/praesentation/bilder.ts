/// <reference types="next/image-types/global" />
import type { StaticImageData } from "next/image";

/**
 * Bildschirmfotos für das Fenster „Blick in die App“ (Szenen falsche-zahl, kern, beleg, fallen; #59). Nur echte
 * Aufnahmen aus der App, ohne Beschriftung. Ein Bild aufnehmen: Datei nach web/content/slides/bilder/SC07.png
 * legen und hier statisch importieren, z. B.
 *
 *   import SC07 from "../../content/slides/bilder/SC07.png";
 *   export const BILDER = { SC07 };
 *
 * Schlüssel ist die Kennung aus `screenshot:` im Frontmatter, zweistellig (`SC07`). Fehlt sie hier, zeigt die Szene
 * kein Fenster und lässt den Platz leer. Der Verweis oben bringt die PNG-Typen von Next auch in die CI (ohne
 * next-env.d.ts).
 */
export const BILDER: Readonly<Record<string, StaticImageData>> = {};

/** Bild zu einer Kennung wie `SC07`, oder `undefined`. */
export function bildFuer(kennung: string | undefined): StaticImageData | undefined {
  return kennung !== undefined && Object.hasOwn(BILDER, kennung) ? BILDER[kennung] : undefined;
}
