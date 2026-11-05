import { useId, type InputHTMLAttributes } from "react";
import { fokus, klassen } from "./klassen";
import { Status } from "./status";

export type FeldProps = Omit<InputHTMLAttributes<HTMLInputElement>, "autoFocus"> & {
  label: string;
  /** Kurzer Hinweis unter der Eingabe, z. B. das erwartete Format. */
  hinweis?: string;
  /** Fehlermeldung; setzt `aria-invalid` und ersetzt optisch den Hinweis nicht. */
  fehler?: string;
};

/** Feld aus Label, Eingabe und Hinweis. Hinweis und Fehler sind per `aria-describedby` verknüpft. */
export function Feld({ label, hinweis, fehler, id, className, ...rest }: FeldProps) {
  const eigeneId = useId();
  const feldId = id ?? eigeneId;
  const hinweisId = hinweis ? `${feldId}-hinweis` : undefined;
  const fehlerId = fehler ? `${feldId}-fehler` : undefined;
  const { autoFocus: _verworfen, ...erlaubt } = rest as typeof rest & { autoFocus?: boolean };
  return (
    <div className={klassen("flex flex-col gap-2", className)}>
      <label htmlFor={feldId} className="font-sans text-14 font-semibold text-ink">
        {label}
      </label>
      <input
        id={feldId}
        aria-describedby={[hinweisId, fehlerId].filter(Boolean).join(" ") || undefined}
        aria-invalid={fehler ? true : undefined}
        className={klassen(
          "h-10 rounded border bg-white px-3 font-sans text-16 text-ink placeholder:text-slate",
          fehler ? "border-err-fg" : "border-slate",
          fokus,
        )}
        {...erlaubt}
      />
      {hinweis && (
        <p id={hinweisId} className="font-sans text-12 text-slate">
          {hinweis}
        </p>
      )}
      {fehler && (
        <Status id={fehlerId} art="fehler">
          {fehler}
        </Status>
      )}
    </div>
  );
}
