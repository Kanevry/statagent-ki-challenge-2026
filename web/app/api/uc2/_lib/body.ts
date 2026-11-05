// Body lesen mit harter Grenze: gezählt wird beim Lesen, auch ohne Content-Length (gestreamte Anfragen).

export class ZuGross extends Error {}

export async function leseBodyText(anfrage: Request, grenze: number): Promise<string> {
  const laenge = Number(anfrage.headers.get("content-length") ?? "");
  if (Number.isFinite(laenge) && laenge > grenze) throw new ZuGross();
  if (!anfrage.body) return "";
  const leser = anfrage.body.getReader();
  const stuecke: Uint8Array[] = [];
  let gelesen = 0;
  for (;;) {
    const { done, value } = await leser.read();
    if (done) break;
    gelesen += value.byteLength;
    if (gelesen > grenze) {
      await leser.cancel();
      throw new ZuGross();
    }
    stuecke.push(value);
  }
  return new TextDecoder().decode(Buffer.concat(stuecke));
}
