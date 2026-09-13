import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PROTECTED_PATHS = [
  "/dashboard",
  "/admin",
  "/quote",
  "/render",
  "/orders",
  "/production",
  "/purchasing",
  "/inventory",
  "/master-data",
  "/door-cad",
];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isProtected = PROTECTED_PATHS.some((path) => pathname.startsWith(path));
  if (!isProtected) return NextResponse.next();

  const token = request.cookies.get("auth_token")?.value;
  if (!token) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/admin/:path*",
    "/quote/:path*",
    "/render/:path*",
    "/orders/:path*",
    "/production/:path*",
    "/purchasing/:path*",
    "/inventory/:path*",
    "/master-data/:path*",
    "/door-cad/:path*",
  ],
};
