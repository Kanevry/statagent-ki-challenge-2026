import { bereiche as registry, type BereichId, type UcEintrag } from "../ucs";

// Reine Navigationslogik der Shell (ohne React, ohne Next), damit Header, Schublade und Tests dieselbe Regel nutzen.

export interface AppTab {
  /** Schlüssel für React und Tests: "uebersicht", eine UC-ID oder "praesentation". */
  schluessel: string;
  href: string;
  label: string;
  /** Vorsatz vor dem Namen, z. B. „UC3 · “; schmal ausgeblendet, damit alle Tabs ohne Scrollen sichtbar sind. */
  kuerzel: string;
  /** Name ohne Vorsatz. `label` = `kuerzel` + `name`. */
  name: string;
  /** Nur UC3: Chip „bewertet“. */
  bewertet: boolean;
}

// Kurze Tab-Namen nach Pen-Frame nas8Y. Fehlt ein Eintrag, steht der Name aus der Registry im Tab.
const tabNamen: Partial<Record<BereichId, string>> = {
  uc1: "KI-Lotse",
  uc2: "HealthPolicy",
  uc4: "Einstieg",
};

/** Tabs in Header-Reihenfolge: Übersicht, die Bereiche aus der Registry, Präsentation. */
export function appTabs(ucs: readonly UcEintrag[] = registry): AppTab[] {
  return [
    { schluessel: "uebersicht", href: "/", label: "Übersicht", kuerzel: "", name: "Übersicht", bewertet: false },
    ...ucs.map((uc) => {
      const kuerzel = `${uc.id.toUpperCase()} · `;
      const name = tabNamen[uc.id] ?? uc.name;
      return { schluessel: uc.id, href: uc.route, label: `${kuerzel}${name}`, kuerzel, name, bewertet: uc.bewertet };
    }),
    {
      schluessel: "praesentation",
      href: "/praesentation",
      label: "Präsentation",
      kuerzel: "",
      name: "Präsentation",
      bewertet: false,
    },
  ];
}

export interface Marke {
  /** Produktname in der ersten Zeile. */
  name: string;
  /** Zeile darunter. */
  zeile: string;
}

/**
 * Marke links im Header (Pen-Frame nas8Y). Der bewertete Bereich trägt seinen Produktnamen: auf UC3 steht
 * „StatAgent“. Überall sonst steht „OneShotAndy“, weil UC1, UC2, UC4, Präsentation und Bausteine zur Plattform
 * des Teams gehören und kein eigenes Produkt tragen, das neben dem Tab noch einmal als Marke auftreten müsste.
 */
export function marke(pfad: string, ucs: readonly UcEintrag[] = registry): Marke {
  const bewertet = ucs.find((uc) => uc.bewertet);
  if (bewertet && istAktiv(bewertet.route, pfad)) {
    return { name: bewertet.name, zeile: "von Bernhard Götzendorfer · Team OneShotAndy" };
  }
  return { name: "OneShotAndy", zeile: "von Bernhard Götzendorfer · KI Challenge 2026" };
}

/** Gilt `href` für `pfad` als aktiv? `/` nur exakt, sonst auch Unterseiten (`/uc3/lauf/2025-10`). */
export function istAktiv(href: string, pfad: string): boolean {
  if (href === "/") return pfad === "/";
  return pfad === href || pfad.startsWith(`${href}/`);
}

/** Der App-Header erscheint überall außer auf der Landingpage `/`, die frei rendert. */
export function zeigtHeader(pfad: string): boolean {
  return pfad !== "/";
}

/** UC, dessen Protokoll die Schublade zeigt: der UC der Route, sonst UC3 (bewertet). */
export function protokollUc(pfad: string, ucs: readonly UcEintrag[] = registry): UcEintrag {
  const treffer = ucs.find((uc) => istAktiv(uc.route, pfad));
  if (treffer) return treffer;
  const bewertet = ucs.find((uc) => uc.bewertet) ?? ucs[0];
  if (!bewertet) throw new Error("Registry ohne UC");
  return bewertet;
}
