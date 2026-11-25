import { encode } from "next-auth/jwt";
import { NextResponse } from "next/server";
import { flexAuthOrigin, flexAuthRequest, gmgSessionMaxAge, isRosterKey, relayCodePattern } from "../../../../flex-auth";

const uncached = { "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" };

function restartSignIn(home: URL) {
  // This path starts the existing same-origin LinkedIn flow, so it cannot loop back into the Flex handoff.
  return NextResponse.redirect(new URL("/linkedin-sign-in.html", home), { status: 303, headers: uncached });
}

export async function POST(request: Request) {
  const started = Date.now();
  let phase = "configuration";
  let exchangeStatus: number | undefined;
  let home: URL | undefined;
  try {
    const flex = flexAuthOrigin();
    if (!flex || request.headers.get("origin") !== flex) return new Response("Forbidden", { status: 403, headers: uncached });
    const contentLength = Number(request.headers.get("content-length"));
    if (!contentLength || contentLength > 256 || request.headers.get("content-type")?.split(";")[0] !== "application/x-www-form-urlencoded") {
      return new Response("Invalid sign-in request", { status: 400, headers: uncached });
    }
    const code = new URLSearchParams(await request.text()).get("code");
    if (!code || !relayCodePattern.test(code)) return new Response("Invalid sign-in request", { status: 400, headers: uncached });
    const secret = process.env.NEXTAUTH_SECRET;
    home = new URL(process.env.NEXTAUTH_URL ?? "");
    if (!secret || home.protocol !== "https:") throw new Error("Desk session is unavailable");

    phase = "exchange";
    const exchange = await flexAuthRequest("exchange", { code });
    exchangeStatus = exchange.status;
    if (exchange.status === 401) {
      console.warn("GMG Flex handoff rejected", { exchangeStatus, durationMs: Date.now() - started });
      return restartSignIn(home);
    }
    if (!exchange.ok) throw new Error("Flex exchange unavailable");
    phase = "identity";
    const identity = await exchange.json();
    if (typeof identity.sub !== "string" || !identity.sub || identity.sub.length > 200 ||
        !(identity.rosterKey === null || isRosterKey(identity.rosterKey))) throw new Error("Unexpected Flex identity");

    const name = typeof identity.name === "string" ? identity.name.slice(0, 200) : undefined;
    phase = "session";
    const token = await encode({ token: { sub: identity.sub, name, gmgFlexRosterKey: identity.rosterKey }, secret, maxAge: gmgSessionMaxAge });
    const response = NextResponse.redirect(new URL("/", home), { status: 303, headers: uncached });
    response.cookies.set("__Secure-next-auth.session-token", token, {
      httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: gmgSessionMaxAge,
    });
    return response;
  } catch (error) {
    console.warn("GMG Flex sign-in failed", {
      phase, exchangeStatus, durationMs: Date.now() - started,
      timeout: error instanceof Error && error.name === "TimeoutError",
      networkCode: error instanceof TypeError && typeof error.cause === "object" && error.cause && "code" in error.cause
        ? String(error.cause.code).slice(0, 32) : undefined,
    });
    if (phase === "exchange" && home) return restartSignIn(home);
    return new Response("The sign-in service is temporarily unavailable. Return to the Community Desk and try again.", { status: 503, headers: uncached });
  }
}
