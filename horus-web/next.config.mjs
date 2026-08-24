/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      { source: "/api/v1/articles/:path*", destination: "http://127.0.0.1:8000/api/v1/articles/:path*" },
      { source: "/api/v1/llm/:path*", destination: "http://127.0.0.1:8000/api/v1/llm/:path*" },
      { source: "/api/v1/stock/:path*", destination: "http://127.0.0.1:8000/api/v1/stock/:path*" },
      { source: "/api/v1/topics/:path*", destination: "http://127.0.0.1:8000/api/v1/topics/:path*" },
    ];
  },
  webpack: (config) => {
    // 3d-force-graph WebGL 처리용
    config.externals = [...(config.externals || [])];
    return config;
  },
};

export default nextConfig;
