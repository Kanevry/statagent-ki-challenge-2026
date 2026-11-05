import { Fliesstext, Ueberschrift } from "@kic/ui/basis";
import { FolieAnsicht, NotizBlocks } from "./folie";
import { Schau, type SchauFolie } from "./schau";
import { leseFolien, zeitStart, zeitText } from "../../lib/praesentation/folien";
import { folieAusParam } from "../../lib/praesentation/navigation";

/**
 * Folienschau aus einem Ordner mit Markdown-Folien (#59). Die Folien liest der Server. Folien mit `szene` laufen als
 * animierte Szene, alle anderen im generischen Layout. Navigation und Takte macht `Schau`. Dunkel ist nur die Bühne.
 */
export function PraesentationSeite({ ordner, folieParam }: { ordner?: string; folieParam: string | string[] | undefined }) {
  const folien = leseFolien(ordner);
  const start = folieAusParam(folieParam, folien.length);

  if (folien.length === 0) {
    return (
      <main id="inhalt" tabIndex={-1} className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-2 px-4 py-8">
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
    // Ohne Sprechtext an den Browser: die Szene braucht nur Inhalt und Frontmatter.
    ...(f.szene ? { szene: { id: f.szene, folie: { ...f, notizen: [] } } } : {}),
  }));

  return (
    <main id="inhalt" tabIndex={-1} className="flex min-h-0 flex-1 flex-col">
      <Schau folien={fuerSchau} start={start} />
    </main>
  );
}
