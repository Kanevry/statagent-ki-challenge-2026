import { KARTE_URL, type KartenDaten, type KartenMeta } from "../szene/vertrag";

/**
 * Dekodiert `oesterreich-punkte.bin` (Format: web/landing/szene/vertrag.ts).
 * Wirft bei falscher Länge, damit eine kaputte Datei nicht still eine leere Karte zeichnet.
 */
export function dekodiereKarte(buf: ArrayBuffer, meta: KartenMeta): KartenDaten {
  if (buf.byteLength < 4) throw new Error(`Kartendatei zu kurz: ${buf.byteLength} Bytes`);
  const n = new DataView(buf).getUint32(0, true);
  const erwartet = 4 + n * 5;
  if (buf.byteLength !== erwartet) {
    throw new Error(`Kartendatei hat ${buf.byteLength} Bytes, erwartet ${erwartet} für N=${n}`);
  }
  if (meta.n !== n) throw new Error(`Kartenmeta nennt N=${meta.n}, Datei N=${n}`);
  const qx = new Uint16Array(buf, 4, n);
  const qy = new Uint16Array(buf, 4 + n * 2, n);
  const bl = new Uint8Array(buf, 4 + n * 4, n);
  const x = new Float32Array(n);
  const y = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    x[i] = qx[i] / 65535;
    y[i] = qy[i] / 65535;
  }
  return { n, x, y, bl, meta };
}

/** Lädt Punkte und Meta parallel aus web/public/landing. */
export async function ladeKarte(basis = ""): Promise<KartenDaten> {
  const [punkte, meta] = await Promise.all([
    fetch(basis + KARTE_URL.punkte).then((r) => {
      if (!r.ok) throw new Error(`Kartendatei: HTTP ${r.status}`);
      return r.arrayBuffer();
    }),
    fetch(basis + KARTE_URL.meta).then((r) => {
      if (!r.ok) throw new Error(`Kartenmeta: HTTP ${r.status}`);
      return r.json() as Promise<KartenMeta>;
    }),
  ]);
  return dekodiereKarte(punkte, meta);
}
