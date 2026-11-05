// Die Musterseite /_bausteine ist in der Entwicklung sichtbar, im Produktionsbetrieb nur mit
// KIC_BAUSTEINE=1 (setzt das Anti-Schablonen-Gate, #62).
export function bausteineSichtbar(env: { NODE_ENV?: string; KIC_BAUSTEINE?: string }): boolean {
  return env.NODE_ENV !== "production" || env.KIC_BAUSTEINE === "1";
}
