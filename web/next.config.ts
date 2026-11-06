import path from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

const repoWurzel = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");

// Schlüssel kommen aus ../.env.local (dotenv-cli im dev-Skript) und bleiben serverseitig.
// `standalone` + Tracing ab Repo-Wurzel: der Deploy-Container (#68) nimmt .next/standalone direkt,
// samt Workspace-Paket @kic/ui.
const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: repoWurzel,
  // /praesentation liest web/content/slides/*.md zur Laufzeit (#59); standalone kopiert sie nur so mit.
  outputFileTracingIncludes: {
    "/praesentation": ["./content/slides/**/*"],
    "/praesentation/management": ["./content/slides-management/**/*"],
  },
  transpilePackages: ["@kic/ui"],
  // Kein `env` mit Vapi-Schlüssel: der Knopf holt ihn zur Laufzeit von /api/plattform/voice-config, und nur wenn
  // Voice aktiv ist. Ein NEXT_PUBLIC_-Wert stünde fest im Browser-Code jedes Builds (Review, 05.11.).
};

export default nextConfig;
