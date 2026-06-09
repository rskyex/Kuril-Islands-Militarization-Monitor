// Allow importing .geojson files as modules (handled by the webpack rule in
// next.config.mjs). Used to bundle data/aois.geojson into the app so it is
// available at runtime on hosts (e.g. Vercel) where the repo-root data/ dir is
// not part of the deployment.
declare module "*.geojson" {
  const value: unknown;
  export default value;
}
