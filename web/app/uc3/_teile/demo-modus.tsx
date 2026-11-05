"use client";

import { useCallback, useEffect, useState } from "react";

// Demo-Ansicht für die Vorführung (Persona-Panel 05.11., Grafik): alles 1,25-fach, damit die Jury aus zwei Metern
// lesen kann. Die Typo-Skala der Tokens ist in rem gesetzt, deshalb reicht die Grundschrift des Dokuments.
// Taste D schaltet um, außer beim Schreiben in einem Feld; die Wahl hält für die Sitzung des Browsers.

const FAKTOR = "125%";
const SPEICHER = "kic-uc3-demo";

function istEingabe(ziel: EventTarget | null): boolean {
  if (!(ziel instanceof HTMLElement)) return false;
  return ziel.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(ziel.tagName);
}

/** Taste D wechselt die Demo-Ansicht. Ist sie aktiv, steht oben ein Hinweis mit Knopf zum Beenden. */
export function DemoModus() {
  const [aktiv, setAktiv] = useState(false);

  const setze = useCallback((wert: boolean) => {
    setAktiv(wert);
    try {
      if (wert) sessionStorage.setItem(SPEICHER, "1");
      else sessionStorage.removeItem(SPEICHER);
    } catch {
      // Ohne Speicher gilt die Wahl nur bis zum nächsten Laden.
    }
  }, []);

  useEffect(() => {
    try {
      if (sessionStorage.getItem(SPEICHER) === "1") setAktiv(true);
    } catch {
      // kein Speicher, Standard bleibt
    }
  }, []);

  useEffect(() => {
    const wurzel = document.documentElement;
    wurzel.style.fontSize = aktiv ? FAKTOR : "";
    return () => {
      wurzel.style.fontSize = "";
    };
  }, [aktiv]);

  useEffect(() => {
    function taste(e: KeyboardEvent) {
      if (e.key !== "d" && e.key !== "D") return;
      if (e.altKey || e.ctrlKey || e.metaKey || e.repeat || istEingabe(e.target)) return;
      setze(!aktiv);
    }
    window.addEventListener("keydown", taste);
    return () => window.removeEventListener("keydown", taste);
  }, [aktiv, setze]);

  return (
    <div aria-live="polite" className="contents">
      {aktiv && (
        <p className="flex flex-wrap items-center gap-4 border-b border-line pb-2 font-sans text-14 text-slate">
          Demo-Ansicht: alles 1,25-fach. Taste D schaltet zurück.
          <button
            type="button"
            onClick={() => setze(false)}
            className="font-semibold text-gruen underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen"
          >
            Normale Ansicht
          </button>
        </p>
      )}
    </div>
  );
}
