import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ["react", "react-dom", "three", "@react-three/fiber"]
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/tests/setup.ts",
    fileParallelism: false
  }
});
