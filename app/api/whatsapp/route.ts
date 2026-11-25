import { backendRequest } from "../../../gmg-backend";

const MAX_WEBHOOK_BYTES = 64 * 1024;

async function forward(operation: "whatsapp" | "whatsapp-verify", body: BodyInit, signature?: string) {
  try {
    const { url, headers } = backendRequest(operation);
    if (signature) headers.set("X-Hub-Signature-256", signature);
    const response = await fetch(url, {
      method: "POST", cache: "no-store", redirect: "error", headers, body,
      signal: AbortSignal.timeout(45_000),
    });
    const challenge = operation === "whatsapp-verify" && response.ok ? await response.text() : null;
    return new Response(challenge, {
      status: response.status, headers: { "Cache-Control": "no-store", "Content-Type": "text/plain" },
    });
  } catch {
    return new Response(null, { status: 503 });
  }
}

export async function GET(request: Request) {
  if (process.env.GMG_WHATSAPP_ENABLED !== "1") return new Response(null, { status: 404 });
  const query = new URL(request.url).searchParams;
  const mode = query.get("hub.mode");
  const token = query.get("hub.verify_token");
  const challenge = query.get("hub.challenge");
  if (mode !== "subscribe" || !token || token.length > 256 || !challenge || !/^\d{1,128}$/.test(challenge)) {
    return new Response(null, { status: 403 });
  }
  return forward("whatsapp-verify", JSON.stringify({ mode, token, challenge }));
}

export async function POST(request: Request) {
  if (process.env.GMG_WHATSAPP_ENABLED !== "1") return new Response(null, { status: 404 });
  const signature = request.headers.get("x-hub-signature-256");
  if (!signature || !/^sha256=[a-f0-9]{64}$/.test(signature)) return new Response(null, { status: 401 });
  const reader = request.body?.getReader();
  if (!reader) return new Response(null, { status: 400 });
  const body = new Uint8Array(MAX_WEBHOOK_BYTES);
  let offset = 0;
  try {
    for (let chunk = await reader.read(); !chunk.done; chunk = await reader.read()) {
      if (offset + chunk.value.byteLength > body.byteLength) {
        await reader.cancel();
        return new Response(null, { status: 413 });
      }
      body.set(chunk.value, offset);
      offset += chunk.value.byteLength;
    }
  } catch {
    return new Response(null, { status: 400 });
  } finally {
    reader.releaseLock();
  }
  return forward("whatsapp", body.subarray(0, offset), signature);
}
