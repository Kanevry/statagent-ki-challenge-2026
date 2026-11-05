import type { Metadata } from "next";
import Link from "next/link";
import { Fliesstext, knopfKlassen, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { findeUc } from "@kic/ui/ucs";

// Platzhalter für die Präsentation vor der Jury; der Inhalt kommt mit #59. Die Protokoll-Schublade zeigt hier UC3.
export const metadata: Metadata = { title: "Präsentation · OneShotAndy" };

export default function Praesentation() {
  const bewertet = findeUc("uc3");
  return (
    <main id="inhalt" tabIndex={-1} className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 px-4 py-8 md:px-8">
      <div className="flex max-w-3xl flex-col gap-2">
        <Ueberschrift stufe={2} als="h1">
          Präsentation
        </Ueberschrift>
        <Fliesstext ton="gedaempft">Hier zeigen wir der Jury den Ablauf von {bewertet.name} Schritt für Schritt.</Fliesstext>
      </div>
      <Leerzustand
        satz="Die Präsentation ist noch nicht eingerichtet."
        aktion={
          <Link href={bewertet.route} className={knopfKlassen("sekundaer")}>
            {`${bewertet.name} öffnen`}
          </Link>
        }
      />
    </main>
  );
}
