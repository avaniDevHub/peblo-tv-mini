import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The CMS talks to the API. In docker-compose we pass VITE_API_BASE at build.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, host: true },
});
