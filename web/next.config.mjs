import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // This is a monorepo: the Next app lives in web/ while the pipeline and the
  // committed seed data live at the repo root. The seed data is imported by
  // src/lib/data.ts so it gets bundled into the server functions — this works
  // on Vercel, where the repo-root data/ dir is NOT part of the deployment.
  // Point tracing at the repo root so that resolution is unambiguous.
  experimental: {
    outputFileTracingRoot: path.join(__dirname, ".."),
  },
  webpack: (config) => {
    // Allow importing GeoJSON files as JSON modules (webpack 5 asset type),
    // so data/aois.geojson can be bundled like the .json seed files.
    config.module.rules.push({ test: /\.geojson$/, type: "json" });
    return config;
  },
};

export default nextConfig;
