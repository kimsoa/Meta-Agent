"""
Meta-Agent Builder — FastAPI Web Application

Endpoints:
  GET  /                      → SPA or welcome page
  GET  /api/agent-types       → list all available agent types
  GET  /api/models            → list available Ollama models
  POST /api/analyze           → analyze a job description
  POST /api/recommend         → analyze + recommend agent type
  POST /api/build             → full pipeline: analyze + recommend + system prompt
  POST /api/chat              → chat with a generated agent via Ollama (streaming SSE)
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from main import MetaAgentBuilder

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemma3:latest")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Meta-Agent Builder API",
    description=(
        "Analyzes job descriptions and generates specialized AI agent configurations "
        "including agent-type recommendations and ready-to-use system prompts. "
        "Connects to Ollama to power real agent conversations."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_builder = MetaAgentBuilder()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class JobDescriptionRequest(BaseModel):
    job_description: str = Field(
        ...,
        min_length=20,
        description="The job description or task specification for the agent to fulfill.",
        example=(
            "We need an AI agent to handle customer service for an e-commerce platform. "
            "It should answer questions, check order status via our database, send emails, "
            "remember conversation history, and escalate to human agents when needed."
        ),
    )


class AnalysisResponse(BaseModel):
    domain: str
    complexity_level: int
    interaction_type: str
    required_capabilities: List[str]
    problem_type: str
    autonomy_level: str
    performance_requirements: Dict[str, str]


class RecommendationResponse(BaseModel):
    agent_type: str
    rationale: str
    characteristics: List[str]
    use_cases: List[str]
    required_tools: List[str]
    safety_considerations: List[str]
    performance_profile: Dict[str, str]


class BuildResponse(BaseModel):
    analysis: AnalysisResponse
    recommendation: RecommendationResponse
    system_prompt: str


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    system_prompt: str = Field(..., min_length=10)
    messages: List[Message]
    model: str = Field(default=DEFAULT_MODEL)


# ---------------------------------------------------------------------------
# Helper — Ollama streaming
# ---------------------------------------------------------------------------

async def _stream_ollama(
    system_prompt: str, messages: List[Message], model: str
) -> AsyncIterator[str]:
    """Yield SSE-formatted chunks from Ollama streaming chat."""
    payload = {
        "model": model,
        "stream": True,
        "messages": [{"role": "system", "content": system_prompt}]
        + [{"role": m.role, "content": m.content} for m in messages],
    }

    timeout = httpx.Timeout(connect=10.0, read=None, write=None, pool=None)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                yield f"data: {json.dumps({'error': body.decode()})}\n\n"
                return

            async for raw in resp.aiter_lines():
                if not raw.strip():
                    continue
                try:
                    chunk = json.loads(raw)
                    token = chunk.get("message", {}).get("content", "")
                    done = chunk.get("done", False)
                    yield f"data: {json.dumps({'token': token, 'done': done})}\n\n"
                    if done:
                        break
                except json.JSONDecodeError:
                    continue


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["Meta"])
def health():
    return {"status": "ok", "ollama_url": OLLAMA_URL, "default_model": DEFAULT_MODEL}


@app.get("/api/agent-types", response_model=Dict[str, Any], tags=["Reference"])
def get_agent_types():
    return _builder.agent_types


@app.get("/api/models", tags=["Reference"])
async def get_models():
    """Return available Ollama models."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            return {"models": models, "default": DEFAULT_MODEL}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Ollama unreachable: {exc}")


@app.post("/api/analyze", response_model=AnalysisResponse, tags=["Pipeline"])
def analyze(request: JobDescriptionRequest):
    try:
        result = _builder.analyze_job_description(request.job_description)
        return AnalysisResponse(
            domain=result["domain"],
            complexity_level=result["complexity_level"],
            interaction_type=result["interaction_type"],
            required_capabilities=result["required_capabilities"],
            problem_type=result["problem_type"],
            autonomy_level=result["autonomy_level"],
            performance_requirements=result["performance_requirements"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/recommend", response_model=RecommendationResponse, tags=["Pipeline"])
def recommend(request: JobDescriptionRequest):
    try:
        analysis = _builder.analyze_job_description(request.job_description)
        _, rec = _builder.recommend_agent_type(analysis)
        return RecommendationResponse(
            agent_type=rec["agent_type"],
            rationale=rec["rationale"],
            characteristics=rec["configuration"]["characteristics"],
            use_cases=rec["configuration"]["use_cases"],
            required_tools=rec["required_tools"],
            safety_considerations=rec["safety_considerations"],
            performance_profile=rec["performance_profile"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/build", response_model=BuildResponse, tags=["Pipeline"])
def build_agent(request: JobDescriptionRequest):
    """Full pipeline → analysis + recommendation + system prompt."""
    try:
        analysis = _builder.analyze_job_description(request.job_description)
        _, rec = _builder.recommend_agent_type(analysis)
        system_prompt = _builder.generate_system_prompt(analysis, rec)

        return BuildResponse(
            analysis=AnalysisResponse(
                domain=analysis["domain"],
                complexity_level=analysis["complexity_level"],
                interaction_type=analysis["interaction_type"],
                required_capabilities=analysis["required_capabilities"],
                problem_type=analysis["problem_type"],
                autonomy_level=analysis["autonomy_level"],
                performance_requirements=analysis["performance_requirements"],
            ),
            recommendation=RecommendationResponse(
                agent_type=rec["agent_type"],
                rationale=rec["rationale"],
                characteristics=rec["configuration"]["characteristics"],
                use_cases=rec["configuration"]["use_cases"],
                required_tools=rec["required_tools"],
                safety_considerations=rec["safety_considerations"],
                performance_profile=rec["performance_profile"],
            ),
            system_prompt=system_prompt,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/chat", tags=["Agent"])
async def chat(request: ChatRequest):
    """
    Stream a response from Ollama using the generated system prompt.
    Returns Server-Sent Events (text/event-stream).
    Each event: data: {"token": "...", "done": false}
    Final event:  data: {"token": "", "done": true}
    """
    return StreamingResponse(
        _stream_ollama(request.system_prompt, request.messages, request.model),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Serve built React SPA (production / Docker)
# ---------------------------------------------------------------------------

_static_dir = Path(__file__).parent / "frontend" / "dist"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
else:
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def root():
        return """<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"><title>Meta-Agent Builder</title>
<style>body{font-family:system-ui,sans-serif;max-width:700px;margin:60px auto;padding:0 20px}
h1{color:#2c3e50}a{color:#3498db}.card{background:#f8f9fa;border-radius:8px;padding:20px 24px;
margin:16px 0;border-left:4px solid #3498db}code{background:#eee;padding:2px 6px;border-radius:3px}</style>
</head><body>
<h1>&#129302; Meta-Agent Builder API</h1>
<p>React UI not yet built. Run <code>cd frontend && npm run build</code> first.</p>
<div class="card"><strong>Docs:</strong> <a href="/docs">Swagger /docs</a> | <a href="/redoc">ReDoc /redoc</a></div>
</body></html>"""
