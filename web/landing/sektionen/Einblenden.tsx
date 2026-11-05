"use client";

import { useEffect, useRef, type ReactNode } from "react";

/** Ein Beobachter für alle Abschnitte statt einem je Instanz. */
let beobachter: IntersectionObserver | null = null;

function gemeinsamerBeobachter(): IntersectionObserver {
  beobachter ??= new IntersectionObserver(
    (eintraege) => {
      for (const e of eintraege) {
        if (!e.isIntersecting) continue;
        (e.target as HTMLElement).dataset.einblenden = "sichtbar";
        beobachter?.unobserve(e.target);
      }
    },
    { rootMargin: "0px 0px -12% 0px" },
  );
  return beobachter;
}

/**
 * Lage ohne erzwungenes Layout: Beim Laden ganz oben und ohne Sprungmarke liegen alle Abschnitte
 * unter der Sticky-Szene (mindestens 360 vh), also sicher unterhalb des Viewports. Nur sonst wird
 * gemessen (die Abschnitte stehen in einer Hülle mit `content-visibility: auto`, eine Messung
 * würde sie sofort layouten).
 */
function unterhalbDesViewports(el: HTMLElement): boolean {
  if (window.scrollY === 0 && !window.location.hash) return true;
  return el.getBoundingClientRect().top >= window.innerHeight;
}

/**
 * Blendet einen Abschnitt einmalig ein, sobald er in den Viewport kommt. Ohne JS, mit reduzierter
 * Bewegung oder wenn der Abschnitt beim Laden schon sichtbar ist, bleibt alles sofort sichtbar:
 * der Wartezustand wird nur gesetzt, solange das Element unterhalb des Viewports liegt.
 * Das Aussehen der Zustände legt das CSS des Abschnitts über `[data-einblenden]` fest.
 */
export default function Einblenden({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (!unterhalbDesViewports(el)) return;

    el.dataset.einblenden = "wartet";
    const b = gemeinsamerBeobachter();
    b.observe(el);
    return () => {
      b.unobserve(el);
      delete el.dataset.einblenden;
    };
  }, []);

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}
