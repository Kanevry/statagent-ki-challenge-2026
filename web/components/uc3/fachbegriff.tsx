import { Begriff } from "@kic/ui/bausteine";
import { UC3_GLOSSAR, type Uc3Begriff } from "./glossar";

/**
 * Fachbegriff mit Erklärung aus dem UC3-Glossar. Standard ist der Untertitel (immer sichtbar, Owner-Vorgabe);
 * `aufNachfrage` nur dort, wo ein Untertitel die Zeile sprengt, etwa in Tabellenköpfen.
 */
export function Fachbegriff({
  wort,
  aufNachfrage = false,
  className,
}: {
  wort: Uc3Begriff;
  aufNachfrage?: boolean;
  className?: string;
}) {
  return <Begriff wort={wort} erklaerung={UC3_GLOSSAR[wort]} untertitel={!aufNachfrage} className={className} />;
}

/**
 * Begriffe eines Abschnitts mit ihren Erklärungen. Ab 768 px stehen sie offen im Raster. Auf dem Handy sind sie
 * eingeklappt („3 Begriffe erklärt“), sonst beginnt der Inhalt bei 390 px erst nach einer Bildschirmhöhe Glossar
 * (Sichtprüfung bb, #18). Die Erklärungen bleiben ein Tippen entfernt und sind für Screenreader gleich.
 */
export function Begriffsliste({
  worte,
  label = "Begriffe in diesem Abschnitt",
  className = "grid gap-4 sm:grid-cols-2",
}: {
  worte: readonly Uc3Begriff[];
  label?: string;
  className?: string;
}) {
  const liste = (
    <ul className={className} aria-label={label}>
      {worte.map((wort) => (
        <li key={wort} className="font-sans text-14 font-semibold text-ink">
          <Fachbegriff wort={wort} />
        </li>
      ))}
    </ul>
  );
  return (
    <>
      <div className="hidden md:block">{liste}</div>
      <details className="md:hidden">
        <summary className="min-h-6 cursor-pointer font-sans text-14 text-ink underline underline-offset-4">
          {`${worte.length === 1 ? "Ein Begriff" : `${worte.length} Begriffe`} erklärt`}
        </summary>
        <div className="pt-2">{liste}</div>
      </details>
    </>
  );
}
