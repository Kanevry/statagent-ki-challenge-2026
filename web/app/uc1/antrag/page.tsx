import type { Metadata } from "next";
import { AntragSeite } from "@/components/uc1/antrag-ansicht";

// /uc1/antrag, Schritt 3 (Pen-Frame ZHSFO): der vorausgefüllte Antrag. Abgeschickt wird nichts.
export const metadata: Metadata = { title: "Antrag · KI-Lotse · OneShotAndy" };

export default function Uc1Antrag() {
  return <AntragSeite />;
}
