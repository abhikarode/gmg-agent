# Tunnel Setup Guide

This document explains how to connect your Vercel-hosted UI to your local AI agent.

## Architecture

```
User → Vercel (UI) → ngrok/Cloudflare Tunnel → Local Machine (Ollama + API)
```

## Prerequisites

1. **ngrok account** (free tier) - https://ngrok.com
2. **Local AI agent running** on port 8000

## Setup Steps

### 1. Start Your Local AI Agent

```bash
# In your gmg-agent directory
source venv/bin/activate
uvicorn api:app --host 0.0.0.0 --port 8000
```

### 2. Install and Configure ngrok

```bash
# Install ngrok (macOS with Homebrew)
brew install ngrok

# Sign up at https://ngrok.com and get your authtoken
# Then configure ngrok:
ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN
```

### 3. Start the Tunnel

```bash
# Start tunnel to port 8000
ngrok http 8000
```

This will output something like:
```
Session Status                online
Account                       Your Name (Plan: Free)
Version                       3.36.1
Region                        United States (us)
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://abc123.ngrok-free.app -> http://localhost:8000
```

### 4. Update Vercel Environment Variable

In your Vercel project settings, set:
```
NEXT_PUBLIC_API_URL=https://abc123.ngrok-free.app/api
```

Replace `abc123.ngrok-free.app` with your actual ngrok URL.

### 5. Deploy to Vercel

1. Push your code to GitHub
2. Import the project to Vercel
3. Set the environment variable in Vercel dashboard
4. Deploy

## Alternative: Cloudflare Tunnel

If you prefer Cloudflare Tunnel:

```bash
# Download cloudflared
curl -L --output cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64
chmod +x cloudflared

# Login to Cloudflare
./cloudflared tunnel login

# Create tunnel
./cloudflared tunnel create gmg-agent

# Run tunnel
./cloudflared tunnel run gmg-agent
```

## Testing

Once everything is set up:

1. Visit your Vercel URL
2. Try asking: "How many members?"
3. You should see the response from your local agent

## Troubleshooting

- **Connection refused**: Make sure your local agent is running on port 8000
- **404 errors**: Check that `NEXT_PUBLIC_API_URL` ends with `/api`
- **CORS errors**: The API has CORS enabled for all origins
- **ngrok not connecting**: Check your authtoken and firewall settings
