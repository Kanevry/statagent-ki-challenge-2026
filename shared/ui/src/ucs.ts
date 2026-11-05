/**
 * Registry der Use Cases (Vertrag H). Header, Landing und die Fallback-Route `web/app/[uc]/` rendern daraus.
 * Reihenfolge = Reihenfolge im Header.
 *
 * Die Registry gehört der Plattform; UC-Lanes schreiben diese Datei nicht (Lead-Entscheid 58). Ein UC hängt
 * sich ein, indem er (1) `web/app/<uc>/` mit `<UcBereich>` anlegt (die statische Route gewinnt gegen den
 * Fallback) und (2) Route-Handler unter `web/app/api/<uc>/**` liefert. Ob ein UC schon Inhalt hat, steht
 * nicht hier: liefert sein `GET /api/<uc>/protokoll` eine leere Liste, zeigt die Schublade den Leerzustand.
 */

export type UcId = "uc1" | "uc2" | "uc3";

export interface UcEintrag {
  id: UcId;
  /** Name des Produkts, z. B. „StatAgent“ */
  name: string;
  /** Ein Satz, was der UC tut */
  kurz: string;
  route: `/${UcId}`;
  /** Nur UC3 wird von der Jury bewertet */
  bewertet: boolean;
}

export const ucs: readonly UcEintrag[] = [
  {
    id: "uc3",
    name: "StatAgent",
    kurz: "Agentengestützter Statistikprozess für die Beschäftigtenstatistik",
    route: "/uc3",
    bewertet: true,
  },
  {
    id: "uc1",
    name: "SV KI-Lotse",
    kurz: "Gesundheits- und Sozialversicherungs-Chatbot mit Belegen",
    route: "/uc1",
    bewertet: false,
  },
  {
    id: "uc2",
    name: "HealthPolicy Simulator",
    kurz: "Multi-Agenten-Simulator für politische, organisatorische und finanzielle Entscheidungen",
    route: "/uc2",
    bewertet: false,
  },
];

export function findeUc(id: UcId): UcEintrag {
  const eintrag = ucs.find((uc) => uc.id === id);
  if (!eintrag) throw new Error(`Unbekannter UC: ${id}`);
  return eintrag;
}
