import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: process.env.NEXT_OUTPUT_STANDALONE === "true" ? "standalone" : undefined,
  // Fix workspace root detection warning for monorepo
  outputFileTracingRoot: __dirname,
};

export default nextConfig;
