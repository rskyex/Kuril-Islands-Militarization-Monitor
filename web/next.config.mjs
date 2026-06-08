/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The event store and AOI config live in ../data (repo root), outside the
  // web app. They are read at request time by server code in src/lib/data.ts.
};

export default nextConfig;
