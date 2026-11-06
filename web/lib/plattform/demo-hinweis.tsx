import { DEMO_HINWEIS } from "@/landing/texte/inhalt";

/** Leiser Hinweis unter dem App-Kopf: die KI-Zugänge werden abgebaut, Rechnen und Ansehen bleiben (Text: DEMO_HINWEIS). */
export function DemoHinweis() {
  return (
    <aside aria-label="Hinweis zur Demo" className="mx-auto w-full max-w-7xl px-4 md:px-8">
      <p className="border-b border-line py-2 font-sans text-14 text-slate">
        {DEMO_HINWEIS.saetze.join(" ")}{" "}
        <a
          href={DEMO_HINWEIS.code.href}
          className="text-ink underline underline-offset-4 hover:text-gruen focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen"
        >
          {DEMO_HINWEIS.code.text}
        </a>
      </p>
    </aside>
  );
}
