import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

let withBundleAnalyzer = (config) => config;
try {
  const bundleAnalyzer = (await import("@next/bundle-analyzer")).default;
  withBundleAnalyzer = bundleAnalyzer({ enabled: process.env.ANALYZE === 'true' });
} catch {
  // @next/bundle-analyzer not installed, skip
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingRoot: __dirname,
  // Build optimizations
  compiler: {
    // ВАЖНО: НЕ удаляем console.log в development для отладки
    removeConsole: false,
    styledComponents: true,
  },
  // Development optimizations with cache control
  productionBrowserSourceMaps: false,
  experimental: {
    optimizeCss: true,
    optimizePackageImports: ['lucide-react', '@radix-ui/react-dialog'],
    webpackMemoryOptimizations: true,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
  images: {
    unoptimized: false,
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000',
  },
  // Prevent excessive caching that fills disk
  onDemandEntries: {
    maxInactiveAge: 25 * 1000, // 25 seconds
    pagesBufferLength: 2, // Keep only 2 pages in memory
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Robots-Tag", value: "noindex, nofollow" },
          {
            key: "Content-Security-Policy",
            value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data: blob: https:; font-src 'self' data: https://r2cdn.perplexity.ai https://fonts.gstatic.com https:; connect-src 'self' https: http://127.0.0.1:8000 http://localhost:8000 http://127.0.0.1:9000 http://localhost:9000; frame-ancestors 'none'",
          },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "geolocation=(), microphone=(), camera=()" },
          { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
        ],
      },
      {
        source: "/webmail/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value:
              "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data: blob: https:; font-src 'self' data: https://r2cdn.perplexity.ai https://fonts.gstatic.com https:; connect-src 'self' https: http://127.0.0.1:8000 http://localhost:8000 http://127.0.0.1:9000 http://localhost:9000; frame-ancestors 'self'",
          },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "geolocation=(), microphone=(), camera=()" },
          { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
        ],
      },
    ];
  },
};

export default withBundleAnalyzer(nextConfig);
