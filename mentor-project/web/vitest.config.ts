import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      {
        find: /^monaco-editor\/esm\/.*\?worker$/,
        replacement: fileURLToPath(
          new URL("./tests/stubs/monaco-worker.ts", import.meta.url)
        ),
      },
      {
        find: /^monaco-editor$/,
        replacement: fileURLToPath(
          new URL("./tests/stubs/monaco-editor.ts", import.meta.url)
        ),
      },
    ],
  },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
  },
});
