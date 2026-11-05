import path from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

const repoWurzel = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");

// Schlüssel kommen aus ../.env.local (dotenv-cli im dev-Skript). In den Browser geht nur der
// öffentliche Vapi-Schlüssel; alle anderen bleiben serverseitig.
// `standalone` + Tracing ab Repo-Wurzel: der Deploy-Container (#68) nimmt .next/standalone direkt,
// samt Workspace-Paket @kic/ui.
const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: repoWurzel,
  transpilePackages: ["@kic/ui"],
  env: {
    NEXT_PUBLIC_VAPI_PUBLIC_KEY: process.env.VAPI_PUBLIC_KEY ?? "",
  },
};

export default nextConfig;
