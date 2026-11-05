import type { ReactNode } from "react";
import { findeUc, type UcId } from "../ucs";
import { UcNavigation, type UcNavPunkt } from "./uc-navigation";

export interface UcBereichProps {
  uc: UcId;
  /** Unter-Navigation des UC; leer = keine Leiste. */
  nav?: readonly UcNavPunkt[];
  children: ReactNode;
}

/**
 * Rahmen eines UC unter dem App-Header: Unter-Navigation, dann der Inhalt als `<main id="inhalt">`.
 * Server-Component-tauglich; ein UC nutzt ihn in `web/app/<uc>/layout.tsx`.
 */
export function UcBereich({ uc, nav = [], children }: UcBereichProps) {
  const eintrag = findeUc(uc);
  return (
    <div data-uc={uc} className="flex flex-1 flex-col">
      {nav.length > 0 && <UcNavigation name={eintrag.name} nav={nav} />}
      <main id="inhalt" tabIndex={-1} className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 px-4 py-8 md:px-8">
        {children}
      </main>
    </div>
  );
}
