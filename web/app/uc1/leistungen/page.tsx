import type { Metadata } from "next";
import { LeistungenSeite } from "@/components/uc1/seiten";

export const metadata: Metadata = { title: "Erkannte Leistungen · KI-Lotse · OneShotAndy" };

export default function Uc1Leistungen() {
  return <LeistungenSeite />;
}
