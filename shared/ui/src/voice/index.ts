// VoiceKnopf (#61): Client-Baustein, das Vapi-SDK kommt über `ladeSdk` aus der App.
export {
  PEGEL_TAKT_MS,
  VOICE_AUS_TEXT,
  VOICE_FEHLER_TEXT,
  VOICE_SPEICHER_HINWEIS,
  VoiceKnopf,
  type VoiceFehler,
  type VoiceKnopfProps,
  type VoiceVorschau,
  type VoiceZustand,
} from "./voice-knopf";
export {
  VOICE_KONFIGURATION_QUELLE,
  voiceKonfigurationSchema,
  type VoiceKonfiguration,
} from "./konfiguration";
export {
  istMikrofonFehler,
  type VoiceNachricht,
  type VoiceSdk,
  type VoiceSdkLader,
  type VoiceTranskript,
} from "./sdk";
