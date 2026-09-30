import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  reactStrictMode: true,

  output:
    process.env.NEXT_OUTPUT_STANDALONE === "true"
      ? "standalone"
      : undefined,

  turbopack: {
    root: path.resolve(__dirname, "../.."),
  },
};

export default nextConfig;