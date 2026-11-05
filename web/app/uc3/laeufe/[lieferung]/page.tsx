import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { istMonat, monatName } from "@/components/uc3/monat";
import { regelsatzAus } from "@/components/uc3/navigation";
import { Monatsseite } from "./_teile/monatsseite";

// Monatsseite (UI-Regie v1): zugleich der Qualitätsbericht des Monats; /uc3/berichte/[monat] rendert dieselbe Seite.
// Ohne Datenbank zeigt sie den Leerzustand (HTTP 200).
export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ lieferung: string }>;
  searchParams: Promise<{ regelsatz?: string | string[] }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { lieferung } = await params;
  return { title: istMonat(lieferung) ? `${monatName(lieferung)} · StatAgent` : "Monat · StatAgent" };
}

export default async function LaufSeite({ params, searchParams }: Props) {
  const { lieferung } = await params;
  if (!istMonat(lieferung)) notFound();
  return <Monatsseite lieferung={lieferung} regelsatz={regelsatzAus((await searchParams).regelsatz)} />;
}
