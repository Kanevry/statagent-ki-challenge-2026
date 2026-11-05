// Zahlen- und Zeitformat der Bausteine. ICU liefert für de-AT ein geschütztes Leerzeichen als
// Tausendertrennung („387 390“) und einen Bindestrich als Minus. Vorgabe ist 387.390 und das echte
// Minuszeichen U+2212, deshalb werden Trennzeichen und Vorzeichen hier gesetzt.
const MINUS = "−";
const GESCHUETZT = " ";

function deAt(format: Intl.NumberFormat, wert: number): string {
  return format
    .formatToParts(wert)
    .map((teil) => {
      if (teil.type === "group") return ".";
      if (teil.type === "minusSign") return MINUS;
      return teil.value;
    })
    .join("");
}

const ganzzahl = new Intl.NumberFormat("de-AT", { maximumFractionDigits: 0 });
const differenz = new Intl.NumberFormat("de-AT", { maximumFractionDigits: 0, signDisplay: "exceptZero" });
const prozent = new Intl.NumberFormat("de-AT", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: "exceptZero",
});

/** Ganze Zahl im Format 387.390. */
export function formatZahl(wert: number): string {
  return deAt(ganzzahl, wert);
}

/** Differenz mit Vorzeichen: +12, −260, 0. */
export function formatDifferenz(wert: number): string {
  return deAt(differenz, wert);
}

/** Prozentwert mit zwei Nachkommastellen und Vorzeichen: −0,07 %. */
export function formatProzent(wert: number): string {
  return `${deAt(prozent, wert)}${GESCHUETZT}%`;
}

/** Unterschied von vorher zu nachher; Prozent ist `null`, wenn vorher 0 ist. */
export function veraenderung(vorher: number, nachher: number): { differenz: number; prozent: number | null } {
  const diff = nachher - vorher;
  return { differenz: diff, prozent: vorher === 0 ? null : (diff / vorher) * 100 };
}

// Feste Zeitzone, damit Server und Browser dieselbe Uhrzeit ausgeben.
const zeitFormat = new Intl.DateTimeFormat("de-AT", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Europe/Vienna",
});

/** ISO-Zeitpunkt als „05.11.2026, 10:12“; ein ungültiger Wert bleibt, wie er ist. */
export function formatZeit(iso: string): string {
  const datum = new Date(iso);
  return Number.isNaN(datum.getTime()) ? iso : zeitFormat.format(datum);
}
