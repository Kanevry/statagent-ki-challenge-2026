"use client";

import { fokus, klassen } from "../basis/klassen";
import { useShell } from "./kontext";
import { istAktiv } from "./navigation";

export interface UcNavPunkt {
  href: string;
  label: string;
}

/** Aktiv ist der Punkt mit dem längsten passenden `href`, damit `/uc3` auf `/uc3/lauf` nicht mitleuchtet. */
export function aktiverPunkt(nav: readonly UcNavPunkt[], pfad: string): string | undefined {
  return nav
    .filter((punkt) => istAktiv(punkt.href, pfad))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;
}

/** Unter-Navigation eines UC direkt unter dem App-Header. */
export function UcNavigation({ name, nav }: { name: string; nav: readonly UcNavPunkt[] }) {
  const { pfad, Verweis } = useShell();
  const aktiv = aktiverPunkt(nav, pfad);
  return (
    <nav aria-label={`${name}, Unterseiten`} className="border-b border-line bg-paper">
      <ul className="mx-auto flex max-w-7xl items-center gap-1 overflow-x-auto whitespace-nowrap px-2 md:px-6">
        {nav.map((punkt) => (
          <li key={punkt.href}>
            <Verweis
              href={punkt.href}
              aria-current={punkt.href === aktiv ? "page" : undefined}
              className={klassen(
                "inline-flex h-10 items-center rounded px-2 font-sans text-14 border-b-2",
                punkt.href === aktiv ? "border-gruen font-semibold text-ink" : "border-transparent text-slate hover:text-ink",
                fokus,
              )}
            >
              {punkt.label}
            </Verweis>
          </li>
        ))}
      </ul>
    </nav>
  );
}
