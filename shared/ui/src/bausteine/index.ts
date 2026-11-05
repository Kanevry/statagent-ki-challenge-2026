// Bausteine der Belegschicht (#60). Bausteine mit Zustand tragen "use client" in ihrer eigenen Datei;
// WarnChip, FehlerChip, Glossar, Namensregel und Formate laufen auch im Server.
export { Begriff, type BegriffProps } from "./begriff";
export { FehlerChip, WarnChip, type ChipProps } from "./chips";
export { formatDifferenz, formatProzent, formatZahl, formatZeit, veraenderung } from "./format";
export {
  FreigabeKarte,
  type FreigabeAntwort,
  type FreigabeEintrag,
  type FreigabeEntscheidung,
  type FreigabeKarteProps,
} from "./freigabe-karte";
export { GLOSSAR, type GlossarWort } from "./glossar";
export { HerkunftChip, type HerkunftChipProps } from "./herkunft-chip";
export { pruefeName, type NamensPruefung } from "./name";
