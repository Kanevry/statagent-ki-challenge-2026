/**
 * Öffentliche API des Szenen-Motors.
 *
 * - `starteSzene(optionen)` (three.js, nur dynamisch laden): startet die Szene auf einem Canvas,
 *   gibt `null` zurück, wenn kein WebGL2-Kontext entsteht.
 * - `berechneLayout(breite, hoehe, variante, kartenMeta?)` (ohne three.js): DOM-Anker in CSS-Pixeln,
 *   Struktur im Kopf von layout.ts.
 * - `RUHE_P`: Fortschrittswerte, an denen jeder Schritt ruht (für reduzierte Bewegung).
 *
 * Die Seite importiert Layout und Zeitplan direkt aus `./layout` bzw. `./zeitplan`, damit three.js
 * nicht im ersten Bundle landet; dieses Modul zieht three.js mit.
 */
export { starteSzene, ruhendesP, LAYOUT_EVENT, LADEN_MS, GLAETTUNG_S, ATMEN_PX, type SzeneHandle, type SzeneOptionen } from "./motor";
export { berechneLayout, standardRaender, planePartikel, MIN_BEFUND_PARTIKEL, PUNKT_STIL } from "./layout";
export type { SzeneLayout, Raender, BefundAnker, SaeulenAnker, LandAnker, TabellenZeile, Rechteck, BefundId } from "./layout";
export { RUHE_P, ZEITPLAN, MARKEN } from "./zeitplan";
