import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** 需要登录才能访问的路由前缀 */
const PROTECTED_PATHS = ["/dashboard", "/admin"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 仅检查受保护路由
  const isProtected = PROTECTED_PATHS.some((p) => pathname.startsWith(p));
  if (!isProtected) return NextResponse.next();

  // 检查 auth_token cookie（登录时由 useAuth 写入）
  const token = request.cookies.get("auth_token")?.value;
  if (!token) {
    const loginUrl = new URL("/", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/admin/:path*"],
};
