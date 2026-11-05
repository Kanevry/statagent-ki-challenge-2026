import Link from "next/link";
import type { ComponentType } from "react";
import { Fliesstext, knopfKlassen, Ueberschrift } from "@kic/ui/basis";
import { findeUc } from "@kic/ui/ucs";

/**
 * Registry der Routen, die eine `live`-Folie zeigen darf (#59). Der Schlüssel ist die Route aus dem Frontmatter,
 * der Wert eine Komponente, die ohne iframe in die Folie gesetzt wird. Es gibt bewusst keinen dynamischen Import
 * aus dem Markdown: nur was hier steht, wird gerendert.
 */

/** Startseite von StatAgent. Die Komponente liefert nur den Inhalt, den Rahmen (`<main>`) setzt die Folienschau. */
function Uc3Start() {
  const uc = findeUc("uc3");
  return (
    <div className="flex max-w-3xl flex-col items-start gap-4">
      <Ueberschrift stufe={2} als="h2">
        {uc.name}
      </Ueberschrift>
      <Fliesstext ton="gedaempft">{`${uc.kurz}.`}</Fliesstext>
      <Link href={uc.route} className={knopfKlassen("sekundaer")}>
        {`${uc.name} öffnen`}
      </Link>
    </div>
  );
}

// Sobald web/app/uc3/page.tsx auf main liegt, hier stattdessen `import Uc3Seite from "@/app/uc3/page"`
// eintragen. Sie liefert nur Inhalt ohne <main> (den setzt web/app/uc3/layout.tsx).
export const LIVE_ROUTEN: Readonly<Record<string, ComponentType>> = {
  "/uc3": Uc3Start,
};

/** Komponente für eine Route, oder `undefined`, wenn die Route nicht freigegeben ist. */
export function liveKomponente(route: string | undefined): ComponentType | undefined {
  return route !== undefined && Object.hasOwn(LIVE_ROUTEN, route) ? LIVE_ROUTEN[route] : undefined;
}
