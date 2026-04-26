import { resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "./",
  plugins: [react()],
  build: {
    outDir: "src/renderer-dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        pet: resolve(__dirname, "pet.html"),
        dialog: resolve(__dirname, "dialog.html"),
      },
    },
  },
});
