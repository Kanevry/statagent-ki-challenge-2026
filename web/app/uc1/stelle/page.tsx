import type { Metadata } from "next";
import Link from "next/link";
import { Fliesstext, knopfKlassen, Leerzustand, Ueberschrift } from "@kic/ui/basis";

// Noch nicht gebaut (#35, nächste Welle): ein ehrlicher Leerzustand statt einer Attrappe.
export const metadata: Metadata = { title: "Stelle und Termin · KI-Lotse · OneShotAndy" };

export default function Uc1Stelle() {
  return (
    <>
      <div className="flex max-w-3xl flex-col gap-2">
        <Ueberschrift stufe={2} als="h1">
          Stelle und Termin
        </Ueberschrift>
        <Fliesstext ton="gedaempft">Schritt 4 von 4</Fliesstext>
      </div>
      <Leerzustand
        satz="Die zuständige Stelle steht vorerst bei den erkannten Leistungen."
        aktion={
          <Link href="/uc1" className={knopfKlassen("sekundaer")}>
            Zu Meine Situation
          </Link>
        }
      />
    </>
  );
}
