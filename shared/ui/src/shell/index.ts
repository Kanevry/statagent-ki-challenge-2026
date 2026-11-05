// Shell der Plattform (#57, Vertrag H): Header, ModellBadge, Protokoll-Schublade, UcBereich.
// eintrag.ts, modell-status.ts und navigation.ts sind ohne "use client" und auch in Route-Handlern nutzbar.
export { AppShell, type AppShellProps } from "./app-shell";
export { akteure, eintraegeSchema, eintragSchema, eintragStatus, type Akteur, type Eintrag, type EintragStatus } from "./eintrag";
export { AppHeader, type AppHeaderProps } from "./header";
export { ShellAnbieter, useShell, type ShellWert, type Verweis, type VerweisProps } from "./kontext";
export { ModellBadge } from "./modell-badge";
export { modellStatusSchema, modellUnbekannt, type ModellStatus } from "./modell-status";
export { appTabs, istAktiv, protokollUc, zeigtHeader, type AppTab } from "./navigation";
export { ProtokollSchublade, type ProtokollSchubladeProps } from "./protokoll-schublade";
export { UcBereich, type UcBereichProps } from "./uc-bereich";
export { aktiverPunkt, UcNavigation, type UcNavPunkt } from "./uc-navigation";
