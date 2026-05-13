import { NextResponse, type NextRequest } from "next/server";
import { consumeMagicLink, startSession } from "@/lib/auth";
import { recordAudit } from "@/lib/audit";

export async function GET(req: NextRequest) {
  const token = req.nextUrl.searchParams.get("token");
  if (!token) {
    return NextResponse.redirect(new URL("/login?error=missing_token", req.url));
  }
  try {
    const { userId } = await consumeMagicLink(token);
    await startSession(userId);
    await recordAudit({
      userId,
      action: "auth.sign_in",
      metadata: { via: "magic_link" },
    });
    return NextResponse.redirect(new URL("/projects", req.url));
  } catch (err) {
    const msg = encodeURIComponent(err instanceof Error ? err.message : "Invalid link");
    return NextResponse.redirect(new URL(`/login?error=${msg}`, req.url));
  }
}
