const rosterKeyPattern = /^[a-f0-9]{64}$/;
export const relayCodePattern = /^[A-Za-z0-9_-]{43}$/;
export const gmgSessionMaxAge = 8 * 60 * 60;

export function isRosterKey(value: unknown): value is string {
  return typeof value === "string" && rosterKeyPattern.test(value);
}

export function flexAuthOrigin(): string | undefined {
  const value = process.env.GMG_FLEX_AUTH_ORIGIN;
  if (!value) return;
  const url = new URL(value);
  if (url.protocol !== "https:" || url.port || url.username || url.password ||
      !/^[a-z0-9-]+\.azurewebsites\.net$/.test(url.hostname) ||
      url.pathname !== "/" || url.search || url.hash) throw new Error("Invalid Flex authentication origin");
  return url.origin;
}

export async function flexAuthRequest(operation: "exchange" | "membership", body: object) {
  const origin = flexAuthOrigin();
  const secret = process.env.GMG_FLEX_BROKER_SECRET;
  if (!origin || !secret) throw new Error("Flex authentication unavailable");
  return fetch(`${origin}/api/${operation}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${secret}` },
    body: JSON.stringify(body), cache: "no-store", redirect: "error", signal: AbortSignal.timeout(45_000),
  });
}
