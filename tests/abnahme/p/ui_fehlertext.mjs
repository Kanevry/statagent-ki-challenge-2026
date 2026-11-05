// Misst das Verhalten von fehlertext() in der Freigabe-Karte (#135, Kriterium 12), nicht den Quelltext-Wortlaut.
// Die Funktion wird aus dem Quelltext geholt und mit drei Meldungen aufgerufen. Exit 0 nur, wenn alles stimmt.
import { readFileSync } from "node:fs";

const quelle = readFileSync("shared/ui/src/bausteine/freigabe-karte.tsx", "utf8");
const treffer = quelle.match(/function fehlertext\(fehler: unknown\): string \{([\s\S]*?)\n\}/);
if (!treffer) {
  console.log("fehlertext nicht gefunden");
  process.exit(1);
}
const fehlertext = new Function("fehler", treffer[1]);
const anzahl = (t) => (t.match(/nicht gespeichert/gi) ?? []).length;

const fremd = fehlertext(new Error("Bitte später noch einmal versuchen."));
const schon = fehlertext(new Error("Nicht gespeichert. Der Name fehlt."));
const leer = fehlertext(undefined);
const pruefungen = {
  route_satz_einmal: fremd.startsWith("Nicht gespeichert. ") && anzahl(fremd) === 1,
  route_schon_gesagt_einmal: anzahl(schon) === 1,
  leer_fallback: leer.startsWith("Nicht gespeichert.") && anzahl(leer) === 1,
};
for (const [name, ok] of Object.entries(pruefungen)) console.log(`${name} ${ok ? "ja" : "nein"}`);
process.exit(Object.values(pruefungen).every(Boolean) ? 0 : 1);
