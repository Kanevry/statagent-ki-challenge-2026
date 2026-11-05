/**
 * Registry der Bereiche (Vertrag H). Header, Landing, Protokoll-Schublade und die Fallback-Route `web/app/[uc]/`
 * rendern daraus. Reihenfolge = Reihenfolge im Header.
 *
 * Die Registry gehört der Plattform; UC-Lanes schreiben diese Datei nicht (Lead-Entscheid 58). Ein Bereich hängt
 * sich ein, indem er (1) `web/app/<uc>/` mit `<UcBereich>` anlegt (die statische Route gewinnt gegen den
 * Fallback) und (2) Route-Handler unter `web/app/api/<uc>/**` liefert. Ob ein Bereich schon Inhalt hat, steht
 * nicht hier: liefert sein `GET /api/<uc>/protokoll` eine leere Liste, zeigt die Schublade den Leerzustand.
 *
 * Zwei Listen (#98): `ucs` sind genau die drei Use Cases der Ausschreibung (`UcId`; Landing-Texte und die
 * Fallback-Route hängen daran), `bereiche` sind `ucs` plus `uc4`, der gemeinsame Einstieg (`BereichId`). uc4 ist
 * kein eigenes Produkt, sondern die Kette uc3 → uc2 → uc1, und hat immer die eigene Route `web/app/uc4/`.
 * Header, Schublade und `findeUc` lesen `bereiche`.
 */

export type UcId = "uc1" | "uc2" | "uc3";
export type BereichId = UcId | "uc4";

export interface UcEintrag {
  id: BereichId;
  /** Name des Produkts, z. B. „StatAgent“ */
  name: string;
  /** Ein Satz, was der Bereich tut */
  kurz: string;
  route: `/${BereichId}`;
  /** Nur UC3 wird von der Jury bewertet */
  bewertet: boolean;
}

/** Eintrag eines der drei Use Cases (ohne den gemeinsamen Einstieg). */
export type UseCaseEintrag = UcEintrag & { id: UcId; route: `/${UcId}` };

/** Die drei Use Cases. */
export const ucs: readonly UseCaseEintrag[] = [
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

/** Gemeinsamer Einstieg (#98, nicht bewertet): eine Frage läuft durch alle drei Use Cases. */
export const einstieg: UcEintrag = {
  id: "uc4",
  name: "Gemeinsamer Einstieg",
  kurz: "Eine Frage läuft nacheinander durch StatAgent, HealthPolicy Simulator und SV KI-Lotse",
  route: "/uc4",
  bewertet: false,
};

/** Alle Bereiche in Header-Reihenfolge: die drei Use Cases, dann der gemeinsame Einstieg. */
export const bereiche: readonly UcEintrag[] = [...ucs, einstieg];

export function findeUc(id: BereichId): UcEintrag {
  const eintrag = bereiche.find((uc) => uc.id === id);
  if (!eintrag) throw new Error(`Unbekannter Bereich: ${id}`);
  return eintrag;
}
