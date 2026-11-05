// Namensregel für Freigaben, Spiegel von `plattform.freigabe.pruefe_name` (Vertrag P). Die Oberfläche
// schaltet damit den Freigabe-Knopf frei; maßgeblich bleibt die Prüfung im Server. Sperrlisten und
// Wortmuster bei Änderungen in beiden Sprachen nachziehen (Test: tests/bausteine/name.test.ts).

// Wortbestandteile, die auf eine Rolle oder einen Platzhalter statt auf einen Menschen deuten
// („Teamleitung“, „Administrator“, „Mustermann“).
const SPERR_TEILE = ["team", "admin", "agent", "muster"] as const;
// Ganze Wörter, die kein Personenname sind.
const SPERR_WOERTER = new Set([
  "ki", "ai", "bot", "system", "user", "claude", "codex", "gpt", "llm", "modell", "vorname", "nachname",
]);
const WORT = /^\p{L}+(?:[-'’.]\p{L}+)*\.?$/u;
const INITIALE = /^\p{L}\.$/u;
const STEUERZEICHEN = /\p{C}/u;
const BUCHSTABE = /\p{L}/u;

export type NamensPruefung = { gueltig: true; name: string } | { gueltig: false; grund: string };

/** Prüft einen Freigabe-Namen. Gültig: mindestens zwei Wörter aus Buchstaben, keine Rolle, nichts doppelt. */
export function pruefeName(eingabe: string): NamensPruefung {
  if (STEUERZEICHEN.test(eingabe)) {
    return { gueltig: false, grund: "Bitte ohne Zeilenumbruch und ohne Steuerzeichen." };
  }
  if (eingabe.includes(":")) return { gueltig: false, grund: "Bitte ohne Doppelpunkt." };
  const woerter = eingabe.normalize("NFC").split(/\s+/).filter(Boolean);
  if (woerter.length < 2) return { gueltig: false, grund: "Bitte Vor- und Nachname eingeben." };
  for (const wort of woerter) {
    const klein = wort.toLowerCase();
    const buchstaben = [...wort].filter((zeichen) => BUCHSTABE.test(zeichen)).length;
    if (!INITIALE.test(wort) && (!WORT.test(wort) || buchstaben < 2)) {
      return { gueltig: false, grund: `„${wort}“ ist kein Namensteil. Bitte nur Buchstaben.` };
    }
    if (SPERR_WOERTER.has(klein.replace(/^\.+|\.+$/g, "")) || SPERR_TEILE.some((teil) => klein.includes(teil))) {
      return { gueltig: false, grund: "Bitte den eigenen Namen eingeben, keine Rolle." };
    }
  }
  if (new Set(woerter.map((wort) => wort.toLowerCase())).size < woerter.length) {
    return { gueltig: false, grund: "Ein Wort kommt doppelt vor." };
  }
  if (woerter.every((wort) => INITIALE.test(wort))) {
    return { gueltig: false, grund: "Bitte den Namen ausschreiben, nicht nur Initialen." };
  }
  return { gueltig: true, name: woerter.join(" ") };
}
