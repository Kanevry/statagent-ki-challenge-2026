// Web-Lint (Antrag #135, Punkt 135-9): ESLint 9 Flat Config für web/ und die Quellen von @kic/ui, die web/ einbindet.
// Bewusst schmal: Regeln, die echte Fehler fangen (Hooks-Regeln, Next-Fehlerregeln, TypeScript-Empfehlungen).
// Stil regelt die Formatierung, nicht der Lint.
import js from "@eslint/js";
import nextPlugin from "@next/eslint-plugin-next";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "next-env.d.ts",
      "playwright-report/**",
      "test-results/**",
      "public/**",
      // Messskript aus impeccable (fremder Code, eigene Lizenz)
      "tests/lib/slop-measure.js",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx,js,mjs}"],
    // Werkzeug-Skripte (landing/werkzeug, Configs) laufen in Node, Seiten-Skripte im Browser.
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
    plugins: { "react-hooks": reactHooks, "@next/next": nextPlugin },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs["core-web-vitals"].rules,
      // Schmale Leerzeichen in Texten sind gewollt (Zahl und Einheit bleiben zusammen).
      "no-irregular-whitespace": ["error", { skipStrings: true, skipTemplates: true, skipJSXText: true }],
      // Unterstrich markiert absichtlich ungenutzte Parameter (Verträge mit fester Signatur). Nur Warnung: ein
      // ungenutzter Import ist kein Fehler im Lauf und soll am Abgabetag keine fremde Lane sperren (#135).
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    },
  },
);
