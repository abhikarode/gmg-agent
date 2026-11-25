"""
FastAPI wrapper for the AI Agent
Provides a RESTful API for the Garje Marathi AI Agent

This can be deployed to any Python hosting service or run locally.
"""

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from azure.core.exceptions import AzureError
from pydantic import BaseModel, Field
from functools import lru_cache
from typing import Optional
from datetime import datetime, timezone
import json
import os
import secrets
import threading
import time
import logging

from ai_agent import AIAgent, DataStore, ModelType, ModelUnavailable
from people_match import MatchResponse, MatchUnavailable, PeopleIndex, recommend
from expertise import CATALOG, MAX_TOPICS, expertise_entries, load_topics, save_topics, validate_topics
from membership import expertise_key, lookup_member
from whatsapp_pilot import MAX_WEBHOOK_BYTES, configured_pilot, handle_inbound, valid_signature
from starlette.concurrency import run_in_threadpool

app = FastAPI(
    title="Garje Marathi AI API",
    description="AI Assistant for Garje Marathi Community",
    version="1.0.0"
)
logger = logging.getLogger(__name__)
INTERNAL_TOKEN = os.getenv("GMG_INTERNAL_TOKEN")
if os.getenv("GMG_REQUIRE_API_TOKEN") == "1" and not INTERNAL_TOKEN:
    raise RuntimeError("GMG_INTERNAL_TOKEN is required when API authorization is enabled.")


def require_backend_token(authorization: str | None = Header(default=None)) -> None:
    if INTERNAL_TOKEN is None:
        return
    if not secrets.compare_digest((authorization or "").encode(), f"Bearer {INTERNAL_TOKEN}".encode()):
        raise HTTPException(status_code=401, detail="Backend authorization required")


def require_private_token(authorization: str | None = Header(default=None)) -> None:
    if not INTERNAL_TOKEN:
        raise HTTPException(status_code=503, detail="Private authentication is unavailable")
    require_backend_token(authorization)

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
_startup_readiness_reported = threading.Event()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    model: Optional[str] = "auto"
    user: Optional[dict[str, Optional[str]]] = None


class ChatResponse(BaseModel):
    response: str
    model: str


class MatchRequest(BaseModel):
    need: str = Field(min_length=8, max_length=600)
    place: str = Field(default="", max_length=90)


class MembershipRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class ExpertiseRequest(BaseModel):
    topics: list[str] = Field(max_length=MAX_TOPICS)


class WhatsAppChallenge(BaseModel):
    mode: str = Field(max_length=16)
    token: str = Field(max_length=256)
    challenge: str = Field(max_length=128, pattern=r"^[0-9]+$")


def require_whatsapp_pilot():
    try:
        pilot = configured_pilot()
    except ValueError:
        raise HTTPException(status_code=503, detail="WhatsApp pilot is unavailable") from None
    if pilot is None:
        raise HTTPException(status_code=404, detail="Not found")
    return pilot


@app.post("/api/whatsapp-verify", dependencies=[Depends(require_private_token)])
def verify_whatsapp(request: WhatsAppChallenge, pilot=Depends(require_whatsapp_pilot)):
    if request.mode != "subscribe" or not secrets.compare_digest(request.token.encode(), pilot.verify_token.encode()):
        raise HTTPException(status_code=403, detail="Invalid webhook verification")
    return PlainTextResponse(request.challenge)


@app.post("/api/whatsapp", dependencies=[Depends(require_private_token)])
async def whatsapp_webhook(request: Request, pilot=Depends(require_whatsapp_pilot)):
    raw_body = bytearray()
    async for part in request.stream():
        if len(raw_body) + len(part) > MAX_WEBHOOK_BYTES:
            return Response(status_code=413)
        raw_body.extend(part)
    if not valid_signature(pilot, bytes(raw_body), request.headers.get("x-hub-signature-256", "")):
        return Response(status_code=401)
    try:
        payload = json.loads(raw_body)
    except (ValueError, RecursionError):
        return Response(status_code=400)
    try:
        await run_in_threadpool(handle_inbound, payload, pilot)
    except (AzureError, KeyError, OSError, TypeError, ValueError) as error:
        logger.warning("WhatsApp reply ledger unavailable: %s", type(error).__name__)
        return Response(status_code=503)
    return Response(status_code=200)


@app.post("/api/membership", dependencies=[Depends(require_private_token)])
def membership(request: MembershipRequest):
    try:
        member_id = lookup_member(request.email, INTERNAL_TOKEN or "")
        return {"key": expertise_key(member_id) if member_id else None}
    except (AzureError, OSError, ValueError, TypeError):
        raise HTTPException(status_code=503, detail="GMG membership is temporarily unavailable") from None


@app.get("/api/expertise", dependencies=[Depends(require_private_token)])
def read_expertise(x_gmg_member: str = Header(pattern=r"^[a-f0-9]{64}$")):
    try:
        return {"catalog": CATALOG, "maxTopics": MAX_TOPICS, "topics": load_topics(x_gmg_member)}
    except (AzureError, OSError, ValueError, TypeError, KeyError):
        raise HTTPException(status_code=503, detail="Expertise is temporarily unavailable") from None


@app.put("/api/expertise", dependencies=[Depends(require_private_token)])
def write_expertise(request: ExpertiseRequest, x_gmg_member: str = Header(pattern=r"^[a-f0-9]{64}$")):
    try:
        validate_topics(request.topics)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    try:
        return {"topics": save_topics(x_gmg_member, request.topics)}
    except (AzureError, OSError, ValueError, TypeError):
        raise HTTPException(status_code=503, detail="Expertise is temporarily unavailable") from None


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


@app.get("/api/ready")
def readiness():
    """Validate the directory and membership roster before serving the desk."""
    start = time.perf_counter()
    try:
        if not get_data_store().get_users():
            raise ValueError("Empty member directory.")
        roster_start = time.perf_counter()
        if os.getenv("GMG_EXPERTISE_TABLE_URL") or os.getenv("GMG_EXPERTISE_TABLE_CONNECTION_STRING"):
            lookup_member("", INTERNAL_TOKEN or "")
    except Exception as error:
        logger.warning("Directory is not ready (%s)", type(error).__name__)
        raise HTTPException(status_code=503, detail="Directory is not ready") from error
    if not _startup_readiness_reported.is_set():
        finished = time.perf_counter()
        logger.info("GMG startup readiness directory_ms=%d membership_ms=%d total_ms=%d",
                    (roster_start - start) * 1000, (finished - roster_start) * 1000, (finished - start) * 1000)
        _startup_readiness_reported.set()
    return {"status": "ready"}


@app.get("/api/stats", dependencies=[Depends(require_backend_token)])
def stats():
    """Return live counts from the current AlmaShines snapshot."""
    return get_data_store().get_stats()


@app.post("/api/chat", dependencies=[Depends(require_backend_token)])
def chat(request: ChatRequest) -> ChatResponse:
    """Send a message to the AI agent"""
    started = time.perf_counter()
    status = "success"
    selected_model = request.model or "auto"
    try:
        # Validate model
        allowed_models = {"auto", "fast", "balanced", "quality"} | {m.value for m in ModelType}
        if selected_model not in allowed_models:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model. Available: {[m.value for m in ModelType]}"
            )
        
        # Initialize agent and get response
        agent = get_agent(selected_model)
        selected_model = agent.model
        message = request.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="A question is required")
        response = agent.chat(message)
        
        return ChatResponse(response=response, model=agent.model)
        
    except HTTPException:
        status = "rejected"
        raise
    except ModelUnavailable:
        status = "model_unavailable"
        raise HTTPException(status_code=503, detail="The language model is temporarily unavailable")
    except Exception:
        status = "error"
        raise HTTPException(status_code=500, detail="The assistant could not complete that request")
    finally:
        _write_query_log(len(request.message), selected_model, status, time.perf_counter() - started)


@app.post("/api/recommendations", dependencies=[Depends(require_backend_token)])
def recommendations(request: MatchRequest) -> MatchResponse:
    need = request.need.strip()
    if len(need) < 8:
        raise HTTPException(status_code=400, detail="Describe what you need")
    started = time.perf_counter()
    status = "success"
    model = ModelType.NEMOTRON_LIGHTNING.value
    try:
        agent = get_agent(model)
        model = agent.model
        result = recommend(
            get_people_index(), need, request.place.strip(), model, agent.complete_people_match,
            rank_payload_limit=2200 if agent.hosted else None,
            fallback_on_plan_failure=agent.hosted,
        )
        if result.ranking == "directory":
            status = "directory_fallback"
        return result
    except MatchUnavailable as error:
        status = "model_unavailable"
        raise HTTPException(status_code=503, detail="AI matching is temporarily unavailable") from error
    except Exception:
        status = "error"
        raise
    finally:
        _write_query_log(len(need), model, status, time.perf_counter() - started)


def _write_query_log(query_length: int, requested_model: str, status: str, elapsed: float) -> None:
    """Append a local audit record without exposing logs through the public API."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query_length": query_length,
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


@lru_cache(maxsize=1)
def get_data_store() -> DataStore:
    connection = os.getenv("GMG_BLOB_CONNECTION_STRING")
    if connection or os.getenv("GMG_BLOB_ACCOUNT_URL"):
        from directory_snapshot import load_snapshot
        start = time.perf_counter()
        snapshot = load_snapshot(connection)
        downloaded = time.perf_counter()
        data = DataStore(snapshot=snapshot)
        logger.info("GMG directory load snapshot_ms=%d exact_index_ms=%d",
                    (downloaded - start) * 1000, (time.perf_counter() - downloaded) * 1000)
        return data
    return DataStore()


def get_people_index() -> PeopleIndex:
    return _people_index(_directory_topics())


def _directory_topics():
    try:
        return expertise_entries()
    except (AzureError, OSError, ValueError, TypeError, KeyError):
        logger.warning("Member expertise is temporarily unavailable")
        return ()


@lru_cache(maxsize=2)
def _directory_view(topics: tuple) -> DataStore:
    data = get_data_store()
    if not topics:
        return data
    by_key = dict(topics)
    return DataStore(snapshot={"jobs": data.get_jobs(), "users": [
        {**user, "_gmg_member_expertise": by_key.get(expertise_key(str(user.get("unique_profile_id", ""))), ())}
        for user in data.get_users()
    ]})


@lru_cache(maxsize=2)
def _people_index(topics: tuple) -> PeopleIndex:
    return PeopleIndex(_directory_view(topics).get_users())


def get_agent(model: str) -> AIAgent:
    """Reuse loaded data and scraped context across requests."""
    return _agent(model, _directory_topics())


@lru_cache(maxsize=8)
def _agent(model: str, topics: tuple) -> AIAgent:
    return AIAgent(model=model, data_store=_directory_view(topics))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
