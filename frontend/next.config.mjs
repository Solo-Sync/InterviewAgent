/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  async rewrites() {
    const backendOrigin = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000"
    return [
      {
        source: "/api/:path*",
        destination: `${backendOrigin}/api/:path*`,
      },
    ]
  },
}

export default nextConfig
