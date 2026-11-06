// Die andere Fassung der Demo: die öffentliche zeigt auf die Live-Vorführung, die Vorführung zurück. Die Adressen kommen zur
// Laufzeit aus der Umgebung und stehen nie im Code. Fehlt der Wert oder ist er keine https-Adresse, gibt es keinen Knopf.

export type Fassung = { adresse: string; art: "live" | "oeffentlich" };

function adresseAus(wert: string | undefined): string | null {
  const roh = wert?.trim();
  if (!roh) return null;
  try {
    const url = new URL(roh);
    return url.protocol === "https:" && !url.username && !url.password ? url.origin : null;
  } catch {
    return null;
  }
}

/** Die Vorführ-Instanz nennt die öffentliche Fassung; sonst gilt die Live-Adresse, falls gesetzt. */
export function fassungAus(umgebung: Readonly<Record<string, string | undefined>>): Fassung | null {
  const oeffentlich = adresseAus(umgebung.KIC_OEFFENTLICHE_ADRESSE);
  if (oeffentlich) return { adresse: oeffentlich, art: "oeffentlich" };
  const live = adresseAus(umgebung.KIC_LIVE_ADRESSE);
  return live ? { adresse: live, art: "live" } : null;
}
