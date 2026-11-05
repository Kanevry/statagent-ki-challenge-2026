"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { knopfKlassen, Leerzustand } from "@kic/ui/basis";
import type { ModellWahl } from "../../app/api/uc2/_lib/vorbereitung";
import { MERKE_FALL } from "./konstanten";
import type { Modus } from "../../app/api/uc2/_lib/proxy";
import { PanelAnsicht } from "./panel-ansicht";
import { useEreignisstrom } from "./use-ereignisstrom";

// Verdrahtung: Strom lesen, bei Modellfehler einen neuen Versuch starten. Die Ansicht selbst ist rein (panel-ansicht).

function PanelLauf({ fallId, modelle, akteureIgnoriert, modus }: { fallId: string; modelle: ModellWahl[]; akteureIgnoriert: boolean; modus: Modus }) {
  const router = useRouter();
  const { zustand, verbindung, neuVerbinden } = useEreignisstrom(fallId);
  const [laedt, setLaedt] = useState(false);
  const [meldung, setMeldung] = useState<string | null>(null);

  useEffect(() => {
    try {
      sessionStorage.setItem(MERKE_FALL, fallId);
    } catch {
      // Ohne Speicher fehlt nur die Abkürzung über den Menüpunkt "Panel".
    }
  }, [fallId]);

  async function neuStarten(provider: ModellWahl["id"] | null) {
    setLaedt(true);
    setMeldung(null);
    const bisher = zustand.provider;
    const wahl = provider ?? (bisher === "azure" || bisher === "claude" || bisher === "ollama" ? bisher : undefined);
    try {
      const antwort = await fetch("/api/uc2/faelle", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ fall: "wartezeiten", ...(wahl ? { provider: wahl } : {}) }),
        cache: "no-store",
      });
      const daten: unknown = await antwort.json().catch(() => null);
      const id = daten && typeof daten === "object" && "fall_id" in daten ? String((daten as { fall_id: unknown }).fall_id) : "";
      if (antwort.ok && id) {
        router.push(`/uc2/panel?fall=${encodeURIComponent(id)}`);
        return;
      }
      const text = daten && typeof daten === "object" && "fehler" in daten ? String((daten as { fehler: unknown }).fehler) : "";
      setMeldung(
        antwort.status === 403 || antwort.status === 405
          ? "Ein neuer Versuch ist in der Online-Demo gesperrt."
          : antwort.status === 409
            ? "Es läuft schon eine Verhandlung."
            : text ||
              (antwort.status === 422
                ? `Das Panel nimmt ${wahl ?? "dieses Modell"} gerade nicht an. Wähle ein anderes Modell.`
                : "Der neue Versuch konnte nicht starten. Das Modell ist weiter nicht erreichbar."),
      );
    } catch {
      setMeldung("Keine Verbindung zum Server.");
    }
    setLaedt(false);
  }

  return (
    <PanelAnsicht
      zustand={zustand}
      verbindung={verbindung}
      fallId={fallId}
      modelle={modelle}
      neuLaedt={laedt}
      neuMeldung={meldung}
      onNeu={neuStarten}
      onNeuVerbinden={neuVerbinden}
      akteureIgnoriert={akteureIgnoriert}
      modus={modus}
    />
  );
}

/** Seite des Panels: ohne Fall in der Adresse führt sie zum zuletzt gestarteten Fall oder zeigt den Leerzustand. */
export function PanelSeite({
  fallId,
  modelle,
  akteureIgnoriert = false,
  modus = "live",
}: {
  fallId: string | null;
  modelle: ModellWahl[];
  akteureIgnoriert?: boolean;
  modus?: Modus;
}) {
  const router = useRouter();
  useEffect(() => {
    if (fallId) return;
    try {
      const gemerkt = sessionStorage.getItem(MERKE_FALL);
      if (gemerkt && /^[A-Za-z0-9_-]{1,64}$/.test(gemerkt)) router.replace(`/uc2/panel?fall=${encodeURIComponent(gemerkt)}`);
    } catch {
      // Kein Speicher, kein Sprung: der Leerzustand bleibt.
    }
  }, [fallId, router]);

  if (!fallId) {
    return (
      <Leerzustand
        satz="Es läuft noch keine Verhandlung. Stell einen Fall oder spiel die aufgezeichnete ab."
        aktion={
          <div className="flex flex-wrap items-center gap-3">
            <Link href="/uc2" className={knopfKlassen()}>
              Fall stellen
            </Link>
            <Link href="/uc2/panel?fall=mock-wartezeiten" className={knopfKlassen("sekundaer")}>
              Aufgezeichnete Verhandlung abspielen
            </Link>
          </div>
        }
      />
    );
  }
  return <PanelLauf key={fallId} fallId={fallId} modelle={modelle} akteureIgnoriert={akteureIgnoriert} modus={modus} />;
}
