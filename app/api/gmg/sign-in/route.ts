import { NextResponse } from "next/server";
import { flexAuthOrigin } from "../../../../flex-auth";

export function GET() {
  try {
    const flex = process.env.GMG_FLEX_ACTIVE === "true" ? flexAuthOrigin() : undefined;
    if (flex) return NextResponse.redirect(`${flex}/api/start`, { headers: { "Cache-Control": "no-store" } });
    return new Response(null, { status: 307, headers: { Location: "/linkedin-sign-in.html", "Cache-Control": "no-store" } });
  } catch {
    return new Response("Sign-in is temporarily unavailable.", { status: 503 });
  }
}
