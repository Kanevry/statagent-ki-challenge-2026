import Link from "next/link";
import type { Regelsatz } from "./navigation";
import { regelsatzName, regelsatzSatz } from "./regelsatz-name";

const STAENDE: readonly Regelsatz[] = ["v1", "v2"];

/**
 * Schalter zwischen den alten Regeln und dem Stand nach den Änderungsaufträgen, mit dem Satz, was der Unterschied ist
 * und warum beide nebeneinanderstehen. `andereZahl`: dieselbe Zahl im anderen Stand, sonst null.
 */
export function RegelsatzWahl({
  aktiv,
  pfad,
  andereZahl = null,
}: {
  aktiv: Regelsatz;
  pfad: (regelsatz: Regelsatz) => string;
  andereZahl?: number | null;
}) {
  return (
    <div className="flex max-w-3xl flex-col gap-2">
      <nav aria-label="Welche Regeln gelten" className="font-sans text-14">
        <ul className="flex w-fit max-w-full overflow-hidden rounded-md border border-line">
          {STAENDE.map((wert) => (
            <li key={wert}>
              <Link
                href={pfad(wert)}
                aria-current={wert === aktiv ? "page" : undefined}
                className={`inline-flex min-h-11 items-center justify-center px-3 text-center ${wert === aktiv ? "bg-ink text-white" : "text-ink hover:bg-paper"}`}
              >
                {regelsatzName(wert)}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <p className="font-sans text-16 text-pretty text-slate">
        {`${regelsatzSatz(aktiv, andereZahl)} Beide Stände bleiben sichtbar, damit man sieht, was die Aufträge geändert haben. `}
        <Link href="/uc3/freigaben" className="whitespace-nowrap text-ink underline underline-offset-4 hover:text-gruen">
          Die drei Aufträge ansehen
        </Link>
      </p>
    </div>
  );
}
