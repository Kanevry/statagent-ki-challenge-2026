import { klassen } from "./klassen";

// Die drei Schritte aus dem Pen (Fall, Panel verhandelt, Antwort), auf U2-0 und U2-1 gleich.

const SCHRITTE = [
  { nr: 1, name: "Fall" },
  { nr: 2, name: "Panel verhandelt" },
  { nr: 3, name: "Antwort" },
];

export function Schritte({ aktiv }: { aktiv: 1 | 2 | 3 }) {
  return (
    <ol className="flex flex-wrap items-center gap-2" aria-label="Schritte">
      {SCHRITTE.map((s, i) => {
        const zustand = s.nr < aktiv ? "fertig" : s.nr === aktiv ? "aktiv" : "offen";
        return (
          <li key={s.nr} className="flex items-center gap-2" data-schritt={s.nr} data-zustand={zustand} aria-current={zustand === "aktiv" ? "step" : undefined}>
            {i > 0 && <span aria-hidden="true" className="h-px w-6 bg-line" />}
            <span
              className={klassen(
                "inline-flex h-8 items-center gap-2 rounded-full px-3 font-sans text-14",
                zustand === "aktiv" && "bg-gruen font-semibold text-white",
                zustand === "fertig" && "bg-gruen-bg text-gruen",
                zustand === "offen" && "border border-line text-slate",
              )}
            >
              <span className="font-mono text-12">{s.nr}</span>
              {s.name}
              {zustand === "fertig" && <span className="sr-only">, erledigt</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

