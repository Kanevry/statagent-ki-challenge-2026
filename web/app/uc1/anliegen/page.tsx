import type { Metadata } from "next";
import Link from "next/link";
import { Fliesstext, knopfKlassen, Leerzustand, Ueberschrift } from "@kic/ui/basis";

// Noch nicht gebaut (#35, nächste Welle): ein ehrlicher Leerzustand statt einer Attrappe.
export const metadata: Metadata = { title: "Bisherige Anliegen · KI-Lotse · OneShotAndy" };

export default function Uc1Anliegen() {
  return (
    <>
      <div className="flex max-w-3xl flex-col gap-2">
        <Ueberschrift stufe={2} als="h1">
          Bisherige Anliegen
        </Ueberschrift>
        <Fliesstext ton="gedaempft">Was Sie den Lotsen schon gefragt haben.</Fliesstext>
      </div>
      <Leerzustand
        satz="Frühere Anliegen zeigt diese Seite noch nicht."
        aktion={
          <Link href="/uc1" className={knopfKlassen("sekundaer")}>
            Zu Meine Situation
          </Link>
        }
      />
    </>
  );
}
