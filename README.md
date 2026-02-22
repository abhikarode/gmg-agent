# Garje Marathi AI Agent

AI Assistant for the Garje Marathi Community - connecting members, jobs, and community information.

## Features

- **Natural Language Queries** - Ask about members, jobs, and community info
- **Local LLM Inference** - Uses Ollama for privacy and control
- **RESTful API** - FastAPI interface for web integration
- **Vercel Ready** - Deploy as serverless function
- **Docker Support** - Containerized deployment

## Quick Start

### Prerequisites

- Python 3.11+
- Ollama installed and running
- Ollama model (mistral or glm-4.7-flash)

### Installation

```bash
# Clone or download this repository

# Install dependencies
pip install -r requirements.txt

# Pull Ollama model (if not already installed)
ollama pull mistral

# Run the agent
python ai_agent.py
```

### Running the API Server

```bash
# Install FastAPI dependencies
pip install fastapi uvicorn

# Run the API server
python api.py

# Or use Docker
docker-compose up --build
```

## API Usage

### Chat Endpoint

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Find member John", "model": "mistral"}'
```

### Vercel Deployment

1. Push this repository to GitHub
2. Import to Vercel
3. The `vercel.json` config handles the deployment
4. Environment variables are loaded from `.env`

## Query Examples

```
- "Find member John"
- "Search member software engineer"
- "Show me jobs"
- "Find job developer"
- "How many members?"
- "What is Garje Marathi?"
- "List jobs in Mumbai"
```

## Project Structure

```
├── ai_agent.py      # Core AI agent with Ollama integration
├── api.py           # FastAPI REST interface
├── almashines_data.json  # Community data
├── main.py          # Legacy entry point
├── vercel.json      # Vercel deployment config
├── Dockerfile       # Container configuration
├── docker-compose.yml  # Docker setup
└── requirements.txt # Python dependencies
```

## Configuration

### Environment Variables

Create a `.env` file with:

```env
ALMASHINES_API_KEY=your_api_key
ALMASHINES_API_SECRET=your_api_secret
OLLAMA_MODEL=mistral
```

## Development

```bash
# Run tests
pytest

# Lint
flake8

# Type check
mypy .
```

## License

MIT License
