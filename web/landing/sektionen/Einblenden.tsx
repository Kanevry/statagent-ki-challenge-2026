"use client";

import { useEffect, useRef, type ReactNode } from "react";

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
    if (el.getBoundingClientRect().top < window.innerHeight) return;

    el.dataset.einblenden = "wartet";
    const beobachter = new IntersectionObserver(
      (eintraege) => {
        if (!eintraege.some((e) => e.isIntersecting)) return;
        el.dataset.einblenden = "sichtbar";
        beobachter.disconnect();
      },
      { rootMargin: "0px 0px -12% 0px" },
    );
    beobachter.observe(el);
    return () => {
      beobachter.disconnect();
      delete el.dataset.einblenden;
    };
  }, []);

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}
