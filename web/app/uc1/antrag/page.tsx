import type { Metadata } from "next";
import Link from "next/link";
import { Fliesstext, knopfKlassen, Leerzustand, Ueberschrift } from "@kic/ui/basis";

// Noch nicht gebaut (#35, nächste Welle): ein ehrlicher Leerzustand statt einer Attrappe.
export const metadata: Metadata = { title: "Antrag vorbereiten · KI-Lotse · OneShotAndy" };

export default function Uc1Antrag() {
  return (
    <>
      <div className="flex max-w-3xl flex-col gap-2">
        <Ueberschrift stufe={2} als="h1">
          Antrag vorbereiten
        </Ueberschrift>
        <Fliesstext ton="gedaempft">Schritt 3 von 4</Fliesstext>
      </div>
      <Leerzustand
        satz="Das Vorbereiten des Antrags kommt mit dem nächsten Stand."
        aktion={
          <Link href="/uc1" className={knopfKlassen("sekundaer")}>
            Zu Meine Situation
          </Link>
        }
      />
    </>
  );
}
