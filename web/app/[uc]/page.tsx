import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Fliesstext, knopfKlassen, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { UcBereich } from "@kic/ui/shell";
import { ucs, type UcEintrag } from "@kic/ui/ucs";

// Leerer UC-Bereich als Fallback für /uc1 /uc2 /uc3, solange ein UC noch keine eigene Route hat. Erzeugt die
// Seite für alle Registry-UCs ohne eigene Route (Lead-Entscheid 58), alles andere ist 404. Legt ein UC
// web/app/<uc>/ an, gewinnt seine statische Route nur im Dev-Server von selbst. Im Build muss er zusätzlich in
// EIGENE_ROUTE stehen: sonst wird /<uc> hier vorgerendert, und eine dynamische Seite des UC antwortet mit 500
// (gemessen !51, Pipeline 41479). Eine feste Liste statt fs.existsSync, weil Turbopack bei variablen Pfaden das
// ganze Projekt traced. An der Registry ändert ein UC dafür nichts.
export const dynamicParams = false;

/** UCs mit eigenem Ordner unter web/app/<uc>/; uc1 und uc2 tragen sich ein, sobald sie einen anlegen. */
const EIGENE_ROUTE = new Set<string>(["uc3"]);

export function generateStaticParams(): Array<{ uc: string }> {
  return ucs.filter((uc) => !EIGENE_ROUTE.has(uc.id)).map((uc) => ({ uc: uc.id }));
}

type Props = { params: Promise<{ uc: string }> };

function finde(id: string): UcEintrag | undefined {
  return ucs.find((uc) => uc.id === id);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const uc = finde((await params).uc);
  return { title: uc ? `${uc.name} · OneShotAndy` : "Nicht gefunden" };
}

export default async function LeererUcBereich({ params }: Props) {
  const uc = finde((await params).uc);
  if (!uc) notFound();
  return (
    <UcBereich uc={uc.id}>
      <div className="flex max-w-3xl flex-col gap-2">
        <Ueberschrift stufe={2} als="h1">
          {uc.name}
        </Ueberschrift>
        <Fliesstext ton="gedaempft">{uc.kurz}.</Fliesstext>
      </div>
      <Leerzustand
        satz="Dieser Bereich ist noch leer, die Oberfläche kommt mit dem nächsten Stand."
        aktion={
          <Link href="/" className={knopfKlassen("sekundaer")}>
            Zur Übersicht
          </Link>
        }
      />
    </UcBereich>
  );
}
