import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Lets a second dev server run from this folder with its own cache (NEXT_DIST_DIR=.next-alt).
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
};

export default nextConfig;
