"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { knopfKlassen } from "@kic/ui/basis";
import type { Modus } from "../../app/api/uc2/_lib/proxy";
import { PanelBuehne } from "./buehne/buehne";
import { MERKE_FALL, MOCK_FALL_ID } from "./konstanten";

// /uc2/panel: Der Fall steht in der Adresse (?fall=...), damit ein Lauf teilbar bleibt. Ohne Fall führt die Seite zum
// zuletzt geöffneten Fall oder bietet genau eine Aktion an: die aufgezeichnete Verhandlung ansehen.

export function PanelSeite({ fallId, modus = "live" }: { fallId: string | null; modus?: Modus }) {
  const router = useRouter();

  useEffect(() => {
    try {
      if (fallId) {
        sessionStorage.setItem(MERKE_FALL, fallId);
        return;
      }
      const gemerkt = sessionStorage.getItem(MERKE_FALL);
      if (gemerkt && /^[A-Za-z0-9_-]{1,64}$/.test(gemerkt)) router.replace(`/uc2/panel?fall=${encodeURIComponent(gemerkt)}`);
    } catch {
      // Ohne Speicher fehlt nur die Abkürzung zum letzten Fall.
    }
  }, [fallId, router]);

  if (!fallId) {
    return (
      <div className="flex min-h-[60vh] flex-col items-start justify-center gap-6">
        <p className="font-display text-28 font-bold text-ink">Es läuft gerade keine Verhandlung.</p>
        <Link href={`/uc2/panel?fall=${MOCK_FALL_ID}`} className={knopfKlassen()}>
          Verhandlung ansehen
        </Link>
      </div>
    );
  }
  return <PanelBuehne key={fallId} fallId={fallId} modus={modus} />;
}
