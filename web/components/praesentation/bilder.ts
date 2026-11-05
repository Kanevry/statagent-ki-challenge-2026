/// <reference types="next/image-types/global" />
import type { StaticImageData } from "next/image";
import freigabeEcht from "../../content/slides/bilder/freigabe-echt.png";

/**
 * Bildschirmfotos für das Fenster „Blick in die App“ (#59). Nur echte Aufnahmen aus der App, zugeschnitten auf ein
 * lesbares Element, ohne Beschriftung. Ein Bild aufnehmen: Datei nach web/content/slides/bilder/ legen, hier statisch
 * importieren und unter der Kennung eintragen, die im Frontmatter unter `screenshot:` steht. Fehlt die Kennung hier,
 * zeigt die Szene kein Fenster und lässt den Platz leer. Der Verweis oben bringt die PNG-Typen von Next auch in die
 * CI (ohne next-env.d.ts).
 */
export const BILDER: Readonly<Record<string, StaticImageData>> = {
  // UC3-Oberfläche aus MR !51: Änderung wartet auf Freigabe, Vorher, Nachher, Unterschied, Feld für den Namen.
  "freigabe-echt": freigabeEcht,
};

/** Bild zu einer Kennung wie `freigabe-echt`, oder `undefined`. */
export function bildFuer(kennung: string | undefined): StaticImageData | undefined {
  return kennung !== undefined && Object.hasOwn(BILDER, kennung) ? BILDER[kennung] : undefined;
}
