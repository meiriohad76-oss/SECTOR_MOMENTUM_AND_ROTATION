/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  async rewrites() {
    // Proxy /api/v1/* to the FastAPI backend so browser clients (which may not
    // have direct access to 127.0.0.1:8000) can call the API via same-origin
    // requests to the Next.js server on port 3100.
    const apiBase = process.env.API_BASE_URL || "http://127.0.0.1:8000";
    return [
      { source: "/api/v1/:path*", destination: `${apiBase}/api/v1/:path*` },
    ];
  },
};

export default nextConfig;
