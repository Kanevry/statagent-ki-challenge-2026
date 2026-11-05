import type { SVGProps } from "react";

// Linien-Piktogramme aus den Pen-Frames (Lucide, 24er Raster, Strich 2). Immer dekorativ: das Wort steht daneben
// oder der Knopf trägt ein `aria-label`. Farbe aus `currentColor`.

const pfade = {
  protokoll: (
    <>
      <path d="M15 12h-5" />
      <path d="M15 8h-5" />
      <path d="M19 17V5a2 2 0 0 0-2-2H4" />
      <path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3" />
    </>
  ),
  schliessen: (
    <>
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </>
  ),
  datenbank: (
    <>
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M3 5v14a9 3 0 0 0 18 0V5" />
      <path d="M3 12a9 3 0 0 0 18 0" />
    </>
  ),
  wechseln: (
    <>
      <path d="m7 15 5 5 5-5" />
      <path d="m7 9 5-5 5 5" />
    </>
  ),
  haken: <path d="M20 6 9 17l-5-5" />,
} as const;

export type PiktogrammName = keyof typeof pfade;

export type PiktogrammProps = Omit<SVGProps<SVGSVGElement>, "name" | "width" | "height"> & {
  name: PiktogrammName;
  /** Kantenlänge in px, Standard 16. */
  groesse?: number;
};

export function Piktogramm({ name, groesse = 16, ...rest }: PiktogrammProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={groesse}
      height={groesse}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      data-piktogramm={name}
      {...rest}
    >
      {pfade[name]}
    </svg>
  );
}
