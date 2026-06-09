/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack: (config) => {
    // Allow importing GeoJSON files as JSON modules (webpack 5 asset type), so
    // data/aois.geojson can be bundled (inlined) like the .json seed files in
    // src/lib/data.ts. Bundling the seed data is what lets the app render on
    // hosts (e.g. Vercel) where the repo-root data/ dir is not deployed.
    config.module.rules.push({ test: /\.geojson$/, type: "json" });
    return config;
  },
};

export default nextConfig;
