import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: process.env.GMG_STANDALONE === "1" ? "standalone" : undefined,
  turbopack: {
    root: process.cwd(),
  },
};

export default nextConfig;
