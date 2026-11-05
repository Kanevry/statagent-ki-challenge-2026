/**
 * Registry der Use Cases (Vertrag H). Header und Landing rendern daraus.
 *
 * Ein UC hängt sich ein, indem er (1) hier nur seinen eigenen Eintrag ändert (meist `status: "aktiv"`),
 * (2) `web/app/<uc>/layout.tsx` mit `<UcBereich>` anlegt und (3) Route-Handler unter `web/app/api/<uc>/**`
 * liefert. Ein Feld je Zeile, damit parallele Änderungen verschiedener UCs ohne Konflikt mergen.
 * Reihenfolge = Reihenfolge im Header.
 */

export type UcId = "uc1" | "uc2" | "uc3";
export type UcStatus = "leer" | "aktiv";

export interface UcEintrag {
  id: UcId;
  /** Name des Produkts, z. B. „StatAgent“ */
  name: string;
  /** Ein Satz, was der UC tut */
  kurz: string;
  route: `/${UcId}`;
  /** Nur UC3 wird von der Jury bewertet */
  bewertet: boolean;
  status: UcStatus;
}

export const ucs: readonly UcEintrag[] = [
  {
    id: "uc3",
    name: "StatAgent",
    kurz: "Agentengestützter Statistikprozess für die Beschäftigtenstatistik",
    route: "/uc3",
    bewertet: true,
    status: "leer",
  },
  {
    id: "uc1",
    name: "SV KI-Lotse",
    kurz: "Gesundheits- und Sozialversicherungs-Chatbot mit Belegen",
    route: "/uc1",
    bewertet: false,
    status: "leer",
  },
  {
    id: "uc2",
    name: "HealthPolicy Simulator",
    kurz: "Multi-Agenten-Simulator für politische, organisatorische und finanzielle Entscheidungen",
    route: "/uc2",
    bewertet: false,
    status: "leer",
  },
];

export function findeUc(id: UcId): UcEintrag {
  const eintrag = ucs.find((uc) => uc.id === id);
  if (!eintrag) throw new Error(`Unbekannter UC: ${id}`);
  return eintrag;
}
