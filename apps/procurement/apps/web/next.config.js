/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@procurement/db", "@procurement/shared", "@procurement/llm"],
  experimental: {
    serverComponentsExternalPackages: ["postgres", "@aws-sdk/client-s3", "bullmq", "ioredis"],
  },
  webpack: (config) => {
    // react-pdf ships its worker as an ESM file; let webpack resolve it.
    config.resolve.alias.canvas = false;
    return config;
  },
};

export default nextConfig;
