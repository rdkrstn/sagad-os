import { createHmac } from "node:crypto";
import { NextResponse } from "next/server";
import { auth } from "../../../../auth";

interface RealtimeTokenPayload {
  expires_at: number;
  organization_id: string;
  role: string;
  user_id: string;
}

function encodeBase64Url(value: Buffer): string {
  return value.toString("base64url");
}

function createRealtimeToken(payload: RealtimeTokenPayload, secret: string): string {
  const payloadBuffer = Buffer.from(JSON.stringify(payload), "utf8");
  const signature = createHmac("sha256", secret).update(payloadBuffer).digest();
  return `${encodeBase64Url(payloadBuffer)}.${encodeBase64Url(signature)}`;
}

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ enabled: false, reason: "unauthorized" }, { status: 401 });
  }

  const wsUrl = process.env.SAGAD_WS_PUBLIC_URL?.trim();
  const secret = process.env.SAGAD_REALTIME_SECRET?.trim();
  if (!wsUrl || !secret) {
    return NextResponse.json({
      enabled: false,
      reason: "Realtime is disabled until SAGAD_WS_PUBLIC_URL and SAGAD_REALTIME_SECRET are configured.",
    });
  }

  if (!session.user.organizationId || !session.user.role) {
    return NextResponse.json({
      enabled: false,
      reason: "Realtime requires an active Sagad organization membership.",
    });
  }

  const expiresAt = Math.floor(Date.now() / 1000) + 60;
  const payload: RealtimeTokenPayload = {
    expires_at: expiresAt,
    organization_id: session.user.organizationId,
    role: session.user.role,
    user_id: session.user.id,
  };

  return NextResponse.json({
    enabled: true,
    token: createRealtimeToken(payload, secret),
    wsUrl,
    expiresAt,
  });
}
