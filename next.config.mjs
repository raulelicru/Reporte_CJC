/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    // xlsx is parsed server-side only; keep it out of client bundles.
    serverComponentsExternalPackages: ["xlsx"],
  },
};

export default nextConfig;
