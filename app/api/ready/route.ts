export const dynamic = "force-dynamic";

export async function GET() {
  const backend = process.env.GMG_API_URL;
  if (backend === "http://127.0.0.1:8000/api") {
    try {
      const response = await fetch(`${backend}/ready`, {
        cache: "no-store",
        redirect: "error",
        signal: AbortSignal.timeout(8_000),
      });
      if (response.ok) return new Response("Ready");
    } catch {
      // During container startup the private sidecar may still be unavailable.
    }
  }
  return new Response("Unavailable", { status: 503 });
}
