import { defineConfig } from "vite";

// The bundle is committed under custom_components/ because HACS does not run
// any build step: users get exactly what is in the repository.
export default defineConfig({
  build: {
    target: "es2022",
    outDir: "../../custom_components/simplex/cards/simplex-messenger-card",
    emptyOutDir: true,
    minify: "esbuild",
    lib: {
      entry: "src/simplex-messenger-card.ts",
      formats: ["es"],
      fileName: () => "simplex-messenger-card.js",
    },
    // Lit is bundled on purpose: Home Assistant does not guarantee that a
    // custom card can import a shared `lit` package.
    rollupOptions: { external: [] },
  },
});
