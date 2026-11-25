import { flexAuthRequest, isRosterKey } from "./flex-auth.ts";

export function backendRequest(operation: string) {
  const base = process.env.GMG_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";
  const token = process.env.GMG_INTERNAL_TOKEN;
  const url = new URL(`${base.replace(/\/+$/, "")}/${operation}`);
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if (!token || (!local && url.protocol !== "https:")) throw new Error("GMG backend unavailable");
  const headers = new Headers({ "Content-Type": "application/json", Authorization: `Bearer ${token}` });
  return { url, headers };
}

export type GmgAccess =
  | { status: "member"; key: string }
  | { status: "unmatched" | "email-unverified" | "unavailable" };

export async function lookupGmgAccess(verifiedEmail: unknown, rosterKey?: unknown): Promise<GmgAccess> {
  const email = typeof verifiedEmail === "string" && verifiedEmail ? verifiedEmail : undefined;
  const key = isRosterKey(rosterKey) ? rosterKey : undefined;
  if (!email && !key) return { status: "email-unverified" };
  try {
    if (key || process.env.GMG_FLEX_ACTIVE === "true") {
      const response = await flexAuthRequest("membership", key ? { rosterKey: key } : { email });
      if (!response.ok) return { status: "unavailable" };
      const { key: memberKey } = await response.json();
      if (isRosterKey(memberKey)) return { status: "member", key: memberKey };
      return { status: memberKey === null ? "unmatched" : "unavailable" };
    }
    const { url, headers } = backendRequest("membership");
    const response = await fetch(url, {
      method: "POST", headers, body: JSON.stringify({ email }),
      cache: "no-store", redirect: "error", signal: AbortSignal.timeout(12_000),
    });
    if (response.ok) {
      const { key } = await response.json();
      if (isRosterKey(key)) return { status: "member", key };
      if (key === null) return { status: "unmatched" };
    }
  } catch {
    // Account access fails closed when the membership service is unreachable.
  }
  return { status: "unavailable" };
}
