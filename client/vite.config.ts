import { defineConfig } from "vite";

// GitHub Pages serves this as a project site at /modern-army/, so the build
// needs that base path; local dev and preview stay at "/".
export default defineConfig({
  base: process.env.VITE_BASE_PATH ?? "/",
});
