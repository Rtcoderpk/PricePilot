/** @type {import('next').NextConfig} */
const nextConfig = {
  // Don't let `next dev` auto-generate AGENTS.md/CLAUDE.md shims in this monorepo —
  // the repo root carries the real project instructions.
  agentRules: false,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "images.openfoodfacts.org" },
      { protocol: "https", hostname: "world.openfoodfacts.org" },
    ],
  },
};

module.exports = nextConfig;