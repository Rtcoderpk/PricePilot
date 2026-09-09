/**
 * Next.js proxy (formerly "middleware" convention) — adds production security
 * headers to every response. Applies on the Node runtime; stays lightweight
 * and dependency-free. See https://nextjs.org/docs (proxy convention).
 */
import { NextRequest, NextResponse } from "next/server";

// Proxy always runs on the Node.js runtime (proxy file convention).

export function proxy(request: NextRequest): NextResponse {
  // Pass through to the next handler and add security headers to the response.
  const response = NextResponse.next();

  // Strict-Transport-Security — HSTS; 1 year, include subdomains.
  response.headers.set(
    "Strict-Transport-Security",
    "max-age=31536000; includeSubDomains",
  );
  // Prevent MIME-type sniffing.
  response.headers.set("X-Content-Type-Options", "nosniff");
  // Referrer-Policy: send origin only on cross-origin; full for same-origin.
  response.headers.set("Referrer-Policy", "origin-when-cross-origin");
  // Permissions-Policy: disable unnecessary browser features.
  response.headers.set(
    "Permissions-Policy",
    "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  );
  // Clickjacking protection — disallow embedding in iframes on other origins.
  response.headers.set("X-Frame-Options", "SAMEORIGIN");
  // Prevent search engines from indexing the app pages.
  response.headers.set("X-Robots-Tag", "noindex, nofollow");
  // Remove server-identifying header if present.
  response.headers.delete("X-Powered-By");

  return response;
}