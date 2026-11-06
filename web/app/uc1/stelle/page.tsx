import { redirect } from "next/navigation";

// /uc1/stelle gibt es nicht mehr als eigene Seite (Urteil der Sichtprüfung): die zuständige Stelle steht im Antrag.
// Alte Links führen dorthin, kein toter Link.
export default function Uc1Stelle() {
  redirect("/uc1/antrag");
}
