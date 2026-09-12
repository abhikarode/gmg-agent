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


class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = "auto"


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
    try:
        # Validate model
        allowed_models = {"auto", "fast", "balanced", "quality"} | {m.value for m in ModelType}
        if request.model not in allowed_models:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model. Available: {[m.value for m in ModelType]}"
            )
        
        # Initialize agent and get response
        selected_model = request.model or "auto"
        agent = get_agent(selected_model)
        response = agent.chat(request.message)
        
        return ChatResponse(response=response, model=agent.model)
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="The assistant could not complete that request")


@lru_cache(maxsize=8)
def get_agent(model: str) -> AIAgent:
    """Reuse loaded data and scraped context across requests."""
    return AIAgent(model=model)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
