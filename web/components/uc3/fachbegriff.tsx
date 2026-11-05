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
