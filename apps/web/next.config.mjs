/** @type {import('next').NextConfig} */
const nextConfig = {
  // Emits .next/standalone with only the files and node_modules actually
  // reached at runtime, which is what the Docker image copies. `next dev` and
  // `next start` are unaffected.
  output: "standalone",

  webpack: (config, { dev }) => {
    if (dev) {
      config.watchOptions = {
        ...config.watchOptions,
        ignored: ["**/node_modules/**", "**/.git/**", "**/.claude/**", "**/.next/**"],
      };
    }
    return config;
  },
};

export default nextConfig;
