#!/bin/bash

# Start ngrok tunnel for local AI agent
# Usage: ./start-tunnel.sh

echo "Starting ngrok tunnel for local AI agent..."
echo "Make sure your local agent is running on port 8000"
echo ""

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "❌ ngrok not found. Installing..."
    brew install ngrok
fi

# Check if ngrok is configured
if [ ! -f ~/.ngrok/ngrok.yml ] && [ ! -f ~/Library/Application\ Support/ngrok/ngrok.yml ]; then
    echo "⚠️  ngrok not configured. Please run:"
    echo "   ngrok config add-authtoken YOUR_AUTHTOKEN"
    echo ""
    echo "Get your authtoken from: https://dashboard.ngrok.com/get-started/your-authtoken"
    exit 1
fi

echo "Starting tunnel to http://localhost:8000"
echo ""
echo "Copy the public URL from the output below and set it as:"
echo "NEXT_PUBLIC_API_URL in your Vercel project"
echo ""
echo "Press Ctrl+C to stop the tunnel"
echo ""

ngrok http 8000
