"""
FastAPI wrapper for the AI Agent
Provides a RESTful API for the Garje Marathi AI Agent

This can be deployed to any Python hosting service or run locally.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from functools import lru_cache
from typing import Optional
from datetime import datetime, timezone
import json
import os
import threading
import time

from ai_agent import AIAgent, DataStore, ModelType

app = FastAPI(
    title="Garje Marathi AI API",
    description="AI Assistant for Garje Marathi Community",
    version="1.0.0"
)

# CORS middleware for web access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in __import__("os").getenv("UI_ORIGINS", "*").split(",")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

QUERY_LOG_PATH = os.getenv("QUERY_LOG_PATH", "query_logs.jsonl")
_query_log_lock = threading.Lock()


class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = "auto"
    user: Optional[dict[str, Optional[str]]] = None


class ChatResponse(BaseModel):
    response: str
    model: str


@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "name": "Garje Marathi AI API",
        "version": "1.0.0",
        "description": "AI Assistant for Garje Marathi Community",
        "endpoints": {
            "/api/chat": "POST - Send a message to the AI",
            "/api/health": "GET - Health check"
        }
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/stats")
async def stats():
    """Return live counts from the current AlmaShines snapshot."""
    return DataStore().get_stats()


@app.post("/api/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a message to the AI agent"""
    started = time.perf_counter()
    status = "success"
    selected_model = request.model or "auto"
    try:
        # Validate model
        allowed_models = {"auto", "fast", "balanced", "quality"} | {m.value for m in ModelType}
        if request.model not in allowed_models:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model. Available: {[m.value for m in ModelType]}"
            )
        
        # Initialize agent and get response
        agent = get_agent(selected_model)
        response = agent.chat(request.message)
        
        return ChatResponse(response=response, model=agent.model)
        
    except HTTPException:
        status = "rejected"
        raise
    except Exception:
        status = "error"
        raise HTTPException(status_code=500, detail="The assistant could not complete that request")
    finally:
        _write_query_log(request, selected_model, status, time.perf_counter() - started)


def _write_query_log(request: ChatRequest, requested_model: str, status: str, elapsed: float) -> None:
    """Append a local audit record without exposing logs through the public API."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_name": (request.user or {}).get("name"),
        "user_email": (request.user or {}).get("email"),
        "query": request.message,
        "requested_model": requested_model,
        "status": status,
        "latency_ms": round(elapsed * 1000),
    }
    try:
        with _query_log_lock:
            with open(QUERY_LOG_PATH, "a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        # Logging must never make the assistant unavailable.
        pass


@lru_cache(maxsize=8)
def get_agent(model: str) -> AIAgent:
    """Reuse loaded data and scraped context across requests."""
    return AIAgent(model=model)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
