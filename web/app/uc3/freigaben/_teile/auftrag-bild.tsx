// Kleine Bilder zu den drei Änderungsaufträgen: was der Auftrag tut, ohne Zahl. Reine Dekoration für das Auge, der Text
// daneben sagt dasselbe, deshalb aria-hidden. Aufträge ohne Nummer aus der Aufgabe bekommen kein Bild.

const rahmen = { width: 64, height: 48, viewBox: "0 0 64 48", "aria-hidden": true, className: "shrink-0 text-gruen" } as const;

function Zusammen() {
  return (
    <svg {...rahmen}>
      <rect x="2" y="8" width="16" height="12" rx="2" fill="currentColor" opacity="0.45" />
      <rect x="2" y="28" width="16" height="12" rx="2" fill="currentColor" opacity="0.45" />
      <path d="M21 14 L33 22 M21 34 L33 26" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" />
      <rect x="36" y="14" width="26" height="20" rx="2" fill="currentColor" />
    </svg>
  );
}

/** Oben ein Punkt am letzten Tag des Monats, unten der ganze Monat als Balken. */
function GanzerMonat() {
  return (
    <svg {...rahmen}>
      <rect x="2" y="8" width="60" height="10" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.45" />
      <circle cx="56" cy="13" r="3.5" fill="currentColor" opacity="0.45" />
      <rect x="2" y="30" width="60" height="10" rx="2" fill="currentColor" />
    </svg>
  );
}

function Liste() {
  return (
    <svg {...rahmen}>
      <rect x="14" y="4" width="36" height="40" rx="2" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M21 14 H43 M21 22 H43 M21 30 H36" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function AuftragBild({ nummer }: { nummer: string | null }) {
  if (nummer === "1") return <Zusammen />;
  if (nummer === "2") return <GanzerMonat />;
  if (nummer === "3") return <Liste />;
  return null;
}
