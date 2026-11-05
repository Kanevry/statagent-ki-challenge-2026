import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { istMonat, monatName } from "@/components/uc3/monat";
import { regelsatzAus } from "@/components/uc3/navigation";
import { Monatsseite } from "../../laeufe/[lieferung]/_teile/monatsseite";

// Qualitätsbericht eines Monats (UI-Regie v1): dieselbe Seite wie /uc3/laeufe/[monat], dort stehen die fünf
// Abschnitte der Vorlage (Überblick, Auffälligkeiten, Rückfragen, Annahmen, Revisionsbedarf). Die Route bleibt für
// Links aus Präsentation und Abgabe erreichbar.
export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ lieferung: string }>;
  searchParams: Promise<{ regelsatz?: string | string[] }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { lieferung } = await params;
  return { title: istMonat(lieferung) ? `Qualitätsbericht ${monatName(lieferung)} · StatAgent` : "Qualitätsbericht · StatAgent" };
}

export default async function Bericht({ params, searchParams }: Props) {
  const { lieferung } = await params;
  if (!istMonat(lieferung)) notFound();
  return <Monatsseite lieferung={lieferung} regelsatz={regelsatzAus((await searchParams).regelsatz)} />;
}
