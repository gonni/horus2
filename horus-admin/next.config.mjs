/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  webpack: (config) => {
    // 3d-force-graph WebGL 처리용
    config.externals = [...(config.externals || [])];
    return config;
  },
};

export default nextConfig;
