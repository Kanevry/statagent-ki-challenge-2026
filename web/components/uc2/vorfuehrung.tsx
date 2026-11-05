// Der eine Hinweis auf der Seite, wenn kein Sprachmodell läuft. Ruhig, kein Fehler-Ton: Vorführmodus heißt, die
// Verhandlung wird aus einer Aufzeichnung abgespielt. Die Kopfzeile sagt dasselbe ("Testbetrieb: keine KI angeschlossen").

export function Vorfuehrhinweis() {
  return (
    <p className="border-l-2 border-line pl-3 font-sans text-14 text-slate" data-testid="uc2-vorfuehrung">
      Vorführmodus: Es läuft eine aufgezeichnete Verhandlung ohne Sprachmodell.
    </p>
  );
}
