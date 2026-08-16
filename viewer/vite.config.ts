import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The viewer reads ONLY the published catalogue via the public API.
export default defineConfig({
  plugins: [react()],
  server: { port: 5174, host: true },
});
