# Garje Marathi AI UI

Next.js chat interface for the Garje Marathi Community AI.

## Setup

```bash
npm install
npm run dev
```

## Environment Variables

Create `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

For production, set this to your ngrok or Cloudflare Tunnel URL.

## Deployment

1. Push to GitHub
2. Import to Vercel
3. Set environment variable `NEXT_PUBLIC_API_URL` to your tunnel URL
4. Deploy

## Tunnel Setup

### Using ngrok

```bash
# Install ngrok (if not installed)
brew install ngrok

# Configure with your account
ngrok config add-authtoken YOUR_AUTHTOKEN

# Start tunnel to local API
ngrok http 8000
```

Set `NEXT_PUBLIC_API_URL` to the ngrok URL (e.g., `https://abc123.ngrok.io`).

### Using Cloudflare Tunnel

```bash
# Install cloudflared
brew install cloudflared

# Login to Cloudflare
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create gmg-agent

# Run tunnel
cloudflared tunnel run gmg-agent
```

## Query Examples

- "Find member Anand"
- "Show me jobs"
- "How many members?"
- "Tell me about the community"

## Refreshing the member index

The source snapshot is intentionally refreshed outside the web request path. Load the credentials from `.env.local` and run:

```bash
python3 refresh_data.py
```

The API reads the refreshed `almashines_data.json` when it starts. The latest verified refresh produced 5,132 members and 36 jobs.

## Ollama profiles

The API accepts `auto`, `fast`, `balanced`, or `quality`. `fast` and `auto` prefer `qwen3:8b` for responsive general assistance, with `mistral:latest` as the fallback; `balanced` uses `gemma4:26b`; `quality` uses `gemma4:31b`. Override with `OLLAMA_MODEL` when needed. Exact member and job lookups bypass the LLM so factual directory answers do not depend on model memory.

## Login providers

LinkedIn is the only sign-in provider. LinkedIn federation uses LinkedIn OpenID Connect and requires `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, and `NEXT_PUBLIC_LINKEDIN_ENABLED=true`. Register the exact NextAuth callback URL in LinkedIn Developer Portal:

```text
https://YOUR_UI_DOMAIN/api/auth/callback/linkedin
```
