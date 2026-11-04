// Static build only: the site reads src/data/family.json (from scripts/export_family.py), no DB.
import { defineConfig } from "astro/config";

export default defineConfig({
  output: "static",
  trailingSlash: "ignore",
  build: { format: "directory" },
});
