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
