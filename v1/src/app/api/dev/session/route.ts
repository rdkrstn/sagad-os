import { NextRequest, NextResponse } from "next/server";
import {
  DEV_SESSION_COOKIE,
  DEV_SESSION_VALUE,
  devSessionEnabled,
} from "@/lib/auth/dev-session";

function safeRedirectTarget(request: NextRequest): URL {
  const fallback = new URL("/", request.url);
  const next = request.nextUrl.searchParams.get("next");

  if (!next || !next.startsWith("/") || next.startsWith("//")) {
    return fallback;
  }

  return new URL(next, request.url);
}

export async function GET(request: NextRequest) {
  if (!devSessionEnabled()) {
    return NextResponse.json({ detail: "Dev sessions are disabled." }, { status: 404 });
  }

  const response = NextResponse.redirect(safeRedirectTarget(request));
  response.cookies.set({
    name: DEV_SESSION_COOKIE,
    value: DEV_SESSION_VALUE,
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 8 * 60 * 60,
  });

  return response;
}

export async function DELETE() {
  const response = NextResponse.json({ ok: true });
  response.cookies.set({
    name: DEV_SESSION_COOKIE,
    value: "",
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });

  return response;
}
