import Link from "next/link";
import { Fliesstext, knopfKlassen, Ueberschrift } from "@kic/ui/basis";

// 404 der App, z. B. /uc9. Rendert im Root-Layout, also mit App-Header.
export default function NichtGefunden() {
  return (
    <main id="inhalt" tabIndex={-1} className="mx-auto flex w-full max-w-7xl flex-1 flex-col items-start gap-6 px-4 py-8 md:px-8">
      <Ueberschrift stufe={2} als="h1">
        Diese Seite gibt es nicht.
      </Ueberschrift>
      <Fliesstext ton="gedaempft">Die Adresse ist falsch oder der Bereich ist nicht freigeschaltet.</Fliesstext>
      <Link href="/" className={knopfKlassen("primaer")}>
        Zur Übersicht
      </Link>
    </main>
  );
}
