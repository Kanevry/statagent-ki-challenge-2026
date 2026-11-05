import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Fliesstext, knopfKlassen, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { UcBereich } from "@kic/ui/shell";
import { ucs, type UcEintrag } from "@kic/ui/ucs";

// Leerer UC-Bereich als Fallback für /uc1 /uc2 /uc3, solange ein UC noch keine eigene Route hat. Erzeugt die
// Seite für alle Registry-UCs (Lead-Entscheid 58), alles andere ist 404. Legt ein UC web/app/<uc>/ an,
// gewinnt seine statische Route gegen diesen Fallback; an der Registry ändert er dafür nichts.
export const dynamicParams = false;

export function generateStaticParams(): Array<{ uc: string }> {
  return ucs.map((uc) => ({ uc: uc.id }));
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
