/**
 * Lädt nur das Präfix der Kartendatei, das die Szene braucht (Format: ../vertrag.ts). Jedes Präfix
 * ist eine geschichtete Stichprobe; mobil reichen die ersten ~14.000 von 60.000 Punkten, die
 * übrigen werden nicht dekodiert.
 */
import { KARTE_URL, type KartenDaten, type KartenMeta } from "../vertrag";

/** Dekodiert die ersten `max` Punkte. Wirft bei falscher Länge oder abweichender Meta. */
export function dekodierePraefix(buf: ArrayBuffer, meta: KartenMeta, max: number): KartenDaten {
  if (buf.byteLength < 4) throw new Error(`Kartendatei zu kurz: ${buf.byteLength} Bytes`);
  const n = new DataView(buf).getUint32(0, true);
  if (buf.byteLength !== 4 + n * 5) throw new Error(`Kartendatei hat ${buf.byteLength} Bytes, erwartet ${4 + n * 5}`);
  if (meta.n !== n) throw new Error(`Kartenmeta nennt N=${meta.n}, Datei N=${n}`);
  const m = Math.max(0, Math.min(n, Math.ceil(max)));
  const qx = new Uint16Array(buf, 4, m);
  const qy = new Uint16Array(buf, 4 + n * 2, m);
  const bl = new Uint8Array(buf.slice(4 + n * 4, 4 + n * 4 + m));
  const x = new Float32Array(m);
  const y = new Float32Array(m);
  for (let i = 0; i < m; i++) {
    x[i] = qx[i] / 65535;
    y[i] = qy[i] / 65535;
  }
  return { n: m, x, y, bl, meta };
}

export async function ladeKartePraefix(max: number, basis = ""): Promise<KartenDaten> {
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
  return dekodierePraefix(punkte, meta, max);
}
