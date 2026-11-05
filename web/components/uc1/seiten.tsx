"use client";

import Link from "next/link";
import { knopfKlassen, Leerzustand } from "@kic/ui/basis";
import { Antworten, BeispielStart } from "./antworten";
import { useLotse } from "./lotse-kontext";
import { Situation } from "./situation";
import { Kopf } from "./teile";

/** /uc1: Situation erzählen (KN6mU, Startzustand ytfvF), darunter die Antworten (B1gvr). */
export function StartSeite({ beispiel }: { beispiel: boolean }) {
  const { verlauf } = useLotse();
  const ergebnis = verlauf.some((w) => w.antwort.verhalten === "antwort");
  return (
    <>
      <BeispielStart aktiv={beispiel} />
      <Kopf titel="Erzählen Sie, was los ist" unter="Mit eigenen Worten. Rückfragen kommen nur, wenn etwas fehlt." schritt={ergebnis ? 2 : 1} />
      <Situation />
      <Antworten />
    </>
  );
}

/** /uc1/leistungen: dieselben Antworten, solange die Seite offen ist; sonst ein Leerzustand. */
export function LeistungenSeite() {
  const { verlauf, lage } = useLotse();
  const anzahl = verlauf.at(-1)?.antwort.leistungen.length ?? 0;
  return (
    <>
      <Kopf
        titel="Das kommt für Sie in Frage"
        unter={anzahl > 0 ? "Jede Angabe hat eine Quelle. Tippen Sie auf „Beleg anzeigen“." : "Hier stehen die Leistungen zu Ihrer Situation."}
        schritt={2}
      />
      {verlauf.length === 0 && lage.art !== "laden" ? (
        <Leerzustand
          satz="Erst eine Situation erzählen, dann stehen hier die passenden Leistungen."
          aktion={
            <Link href="/uc1" className={knopfKlassen("primaer")}>
              Situation erzählen
            </Link>
          }
        />
      ) : (
        <Antworten />
      )}
    </>
  );
}
