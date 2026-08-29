/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@procurement/db", "@procurement/shared", "@procurement/llm"],
  experimental: {
    serverComponentsExternalPackages: ["postgres", "@aws-sdk/client-s3", "bullmq", "ioredis"],
  },
  webpack: (config) => {
    // react-pdf pulls in `canvas` for server-side rendering; we render in the
    // browser, so stub it out.
    config.resolve.alias.canvas = false;
    // Workspace packages use TS-style `.js` import specifiers that point at
    // `.ts` sources. Teach webpack to resolve them.
    config.resolve.extensionAlias = {
      ".js": [".ts", ".tsx", ".js"],
      ".mjs": [".mts", ".mjs"],
    };
    return config;
  },
};

export default nextConfig;
