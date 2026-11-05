import type { Metadata } from "next";
import { Fliesstext, Ueberschrift } from "@kic/ui/basis";
import { FolieAnsicht, NotizBlocks } from "@/components/praesentation/folie";
import { Schau, type SchauFolie } from "@/components/praesentation/schau";
import { leseFolien, zeitStart, zeitText } from "@/lib/praesentation/folien";
import { folieAusParam } from "@/lib/praesentation/navigation";

// Folienschau vor der Jury (#59). Die Folien liegen als Markdown in web/content/slides/ (Format: README dort),
// der Server liest und baut sie, die Navigation im Browser macht `Schau`. Dunkel ist nur die Bühne.
export const metadata: Metadata = { title: "Präsentation · OneShotAndy" };

type Props = { searchParams: Promise<{ folie?: string | string[] }> };

export default async function Praesentation({ searchParams }: Props) {
  const folien = leseFolien();
  const start = folieAusParam((await searchParams).folie, folien.length);

  if (folien.length === 0) {
    return (
      <main id="inhalt" tabIndex={-1} className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-2 px-4 py-8 md:px-8">
        <Ueberschrift stufe={2} als="h1">
          Präsentation
        </Ueberschrift>
        <Fliesstext ton="gedaempft">Es liegen noch keine Folien bereit.</Fliesstext>
      </main>
    );
  }

  const fuerSchau: SchauFolie[] = folien.map((f) => ({
    id: f.id,
    titel: f.titel,
    zeit: zeitStart(f.zeit),
    zeitText: zeitText(f.zeit),
    inhalt: <FolieAnsicht folie={f} />,
    notizen: f.notizen.length > 0 ? <NotizBlocks blocks={f.notizen} /> : null,
  }));

  return (
    <main id="inhalt" tabIndex={-1} className="flex min-h-0 flex-1 flex-col">
      <Schau folien={fuerSchau} start={start} />
    </main>
  );
}
