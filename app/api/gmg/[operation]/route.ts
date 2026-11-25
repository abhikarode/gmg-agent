import { getToken } from "next-auth/jwt";
import type { NextRequest } from "next/server";
import { backendRequest, lookupGmgAccess } from "../../../../gmg-backend";

export const maxDuration = 120;

type RouteContext = { params: Promise<{ operation: string }> };

async function forward(request: NextRequest, context: RouteContext) {
  const { operation } = await context.params;
  if (!((request.method === "GET" && (operation === "stats" || operation === "expertise")) ||
        (request.method === "PUT" && operation === "expertise") ||
        (request.method === "POST" && (operation === "chat" || operation === "recommendations")))) {
    return Response.json({ error: "Unknown operation." }, { status: 404 });
  }
  const identity = await getToken({ req: request });
  if (!identity) {
    return Response.json({ error: "Sign in to use the GMG directory." }, { status: 401 });
  }
  const access = await lookupGmgAccess(identity.gmgVerifiedLinkedInEmail, identity.gmgFlexRosterKey);
  if (access.status === "unavailable") {
    return Response.json({ error: "Membership could not be checked. Try again shortly." }, { status: 503 });
  }
  if (access.status !== "member") {
    return Response.json({ error: "This LinkedIn account has no verified GMG membership." }, { status: 403 });
  }

  try {
    const { url, headers } = backendRequest(operation);
    let body: string | undefined;
    if (operation === "chat") {
      const input = await request.json().catch(() => null);
      const message = typeof input?.message === "string" ? input.message.trim() : "";
      if (!message || message.length > 2000) {
        return Response.json({ error: "Enter a question of up to 2,000 characters." }, { status: 400 });
      }
      body = JSON.stringify({ message });
    } else if (operation === "recommendations") {
      const input = await request.json().catch(() => null);
      const need = typeof input?.need === "string" ? input.need.trim() : "";
      const place = typeof input?.place === "string" ? input.place.trim() : "";
      if (need.length < 8 || need.length > 600 || place.length > 90) {
        return Response.json({ error: "Describe what you need in 8 to 600 characters." }, { status: 400 });
      }
      body = JSON.stringify({ need, place });
    } else if (operation === "expertise") {
      headers.set("X-GMG-Member", access.key);
      if (request.method === "PUT") {
        if (request.headers.get("content-type")?.split(";")[0]?.trim() !== "application/json") {
          return Response.json({ error: "Send expertise selections as JSON." }, { status: 415 });
        }
        const input = await request.json().catch(() => null);
        if (!Array.isArray(input?.topics) || input.topics.length > 8 ||
            input.topics.some((topic: unknown) => typeof topic !== "string" || !/^[a-z0-9-]{1,40}$/.test(topic))) {
          return Response.json({ error: "Select up to eight topics from the expertise list." }, { status: 422 });
        }
        body = JSON.stringify({ topics: input.topics });
      }
    }

    const response = await fetch(url, {
      method: request.method,
      body,
      headers,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(operation === "stats" || operation === "expertise" ? 10_000 : 110_000),
    });
    if (!response.ok) {
      if (operation === "expertise" && response.status === 422) {
        return Response.json({ error: "Choose topics from the current expertise list." }, { status: 422 });
      }
      const status = response.status === 503 ? 503 : 502;
      return Response.json({ error: "The GMG backend could not complete the request." }, { status });
    }
    return Response.json(await response.json(), { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ error: "The GMG backend is unavailable." }, { status: 502 });
  }
}

export { forward as GET, forward as POST, forward as PUT };
