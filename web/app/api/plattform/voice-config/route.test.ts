import { voiceKonfigurationSchema } from "@kic/ui/voice";
import { GET } from "./route";

// Fängt ab: die Route liefert einen geheimen Vapi-Schlüssel an den Browser aus, oder `aktiv` steht auf true,
// obwohl der Custom-LLM-Weg (PUBLIC_URL) fehlt und jedes Gespräch scheitern würde.

const GEHEIM = "geheim-api-schluessel-0000";

beforeEach(() => {
  vi.stubEnv("VAPI_API_KEY", GEHEIM);
  vi.stubEnv("VAPI_WEBHOOK_SECRET", `${GEHEIM}-webhook`);
  vi.stubEnv("VAPI_CUSTOM_LLM_KEY", `${GEHEIM}-llm`);
});
afterEach(() => vi.unstubAllEnvs());

async function lies() {
  const antwort = await GET();
  const text = await antwort.text();
  return { antwort, text, body: voiceKonfigurationSchema.parse(JSON.parse(text)) };
}

describe("GET /api/plattform/voice-config", () => {
  it("liefert öffentlichen Schlüssel und Assistenten, nie VAPI_API_KEY oder andere Geheimnisse", async () => {
    vi.stubEnv("VAPI_PUBLIC_KEY", "pk-oeffentlich");
    vi.stubEnv("VAPI_ASSISTANT_ID", "asst-1");
    vi.stubEnv("PUBLIC_URL", "https://beispiel.example.org");
    const { antwort, text, body } = await lies();
    expect(body).toEqual({ publicKey: "pk-oeffentlich", assistantId: "asst-1", aktiv: true });
    expect(text).not.toContain(GEHEIM);
    expect(Object.keys(JSON.parse(text)).sort()).toEqual(["aktiv", "assistantId", "publicKey"]);
    expect(antwort.headers.get("cache-control")).toBe("no-store");
  });

  it("ist ohne PUBLIC_URL nicht aktiv", async () => {
    vi.stubEnv("VAPI_PUBLIC_KEY", "pk-oeffentlich");
    vi.stubEnv("VAPI_ASSISTANT_ID", "asst-1");
    vi.stubEnv("PUBLIC_URL", "");
    expect((await lies()).body.aktiv).toBe(false);
  });

  it("liefert null statt leerer Werte und ist dann nicht aktiv", async () => {
    vi.stubEnv("VAPI_PUBLIC_KEY", " ");
    vi.stubEnv("VAPI_ASSISTANT_ID", "");
    vi.stubEnv("PUBLIC_URL", "https://beispiel.example.org");
    const { body, text } = await lies();
    expect(body).toEqual({ publicKey: null, assistantId: null, aktiv: false });
    expect(text).not.toContain(GEHEIM);
  });
});
