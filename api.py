"""
Meta-Agent Builder — FastAPI Web Application

Endpoints:
  GET  /                        → SPA or welcome page
  GET  /api/health              → health check + builder identity
  GET  /api/agent-types         → list all available agent types
  GET  /api/models              → list available Ollama models (simple)
  GET  /api/models/discover     → full model catalog: local + external providers
  POST /api/build               → NLP-first build + intelligent model recommendation
  POST /api/chat                → chat with a generated agent via Ollama (streaming SSE)
  GET  /api/tools               → list all tools grouped by ecosystem
  GET  /api/agents              → list all scaffolded agents
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, AsyncIterator, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from main import MetaAgentBuilder
from tool_registry import get_ecosystem_groups
from agent_scaffold import scaffold_agent, list_scaffolded_agents
from docker_agent_scaffold import create_single_docker_agent, create_multi_docker_agent
from model_selector import (
    discover_models,
    recommend_model,
    get_providers_status,
    fetch_provider_models,
    PROVIDER_DEFINITIONS,
)

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

# Legacy kept for /api/analyze backward compat
class JobDescriptionRequest(BaseModel):
    job_description: str = Field(
        ...,
        min_length=20,
        description="The job description or task specification for the agent to fulfill.",
    )


class BuildRequest(BaseModel):
    job_description: str = Field(
        ...,
        min_length=20,
        description="The job description or task specification for the agent to fulfill.",
        example=(
            "We need an AI agent to handle customer service for an e-commerce platform. "
            "It should answer questions, check order status, send emails, and escalate."
        ),
    )
    model: str = Field(default=DEFAULT_MODEL, description="Ollama model to use for NLP analysis")
    scaffold: bool = Field(default=True, description="Whether to scaffold agent microservice folder")


class BuildResponse(BaseModel):
    agent_name: str
    agent_type: str
    domain: str
    sub_domain: str
    complexity_level: int
    interaction_type: str
    autonomy_level: str
    problem_type: str
    required_capabilities: List[str]
    recommended_tools: List[str]
    custom_tools_needed: List[Dict[str, str]]
    rationale: str
    system_prompt: str
    analysis_source: str
    scaffold_path: Optional[str] = None
    # Intelligent model assignment
    recommended_model: Optional[Dict[str, Any]] = None
    builder_model: Optional[Dict[str, Any]] = None


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
async def health():
    """Health check — includes builder identity and Ollama status."""
    catalog = await discover_models(ollama_url=OLLAMA_URL, builder_model=DEFAULT_MODEL)
    return {
        "status": "ok",
        "ollama_url": OLLAMA_URL,
        "builder": catalog["builder"],
        "local_models_count": len(catalog["local"]),
        "configured_providers": catalog["configured_providers"],
    }


@app.get("/api/agent-types", response_model=Dict[str, Any], tags=["Reference"])
def get_agent_types():
    return _builder.agent_types


@app.get("/api/models", tags=["Reference"])
async def get_models():
    """Return available Ollama chat models (simple list for the builder dropdown)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [
                m["name"] for m in data.get("models", [])
                if not any(k in m["name"].lower() for k in ("embed", "bert", "e5-", "bge-"))
            ]
            return {"models": models, "default": DEFAULT_MODEL}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Ollama unreachable: {exc}")


@app.get("/api/models/discover", tags=["Reference"])
async def get_models_discover():
    """
    Full model catalog: discovers all local Ollama models, all external
    providers configured via ENV vars, and the meta-agent builder identity.
    """
    catalog = await discover_models(ollama_url=OLLAMA_URL, builder_model=DEFAULT_MODEL)
    return catalog


@app.get("/api/providers", tags=["Reference"])
async def list_providers():
    """
    Returns all supported model providers, each with a `configured` flag
    indicating whether the provider is reachable or has an API key set.
    """
    providers = await get_providers_status(
        ollama_url=OLLAMA_URL,
        dmr_url=os.getenv("DMR_URL", "http://host-gateway:12434"),
    )
    return {"providers": providers}


@app.get("/api/providers/{provider_id}/models", tags=["Reference"])
async def get_provider_models(provider_id: str):
    """
    Fetch the model list for a specific provider.
    - Local providers: live query their API.
    - Cloud providers with a key in ENV: live query.
    - Others: return the curated catalogue entries.
    """
    if provider_id not in PROVIDER_DEFINITIONS:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_id!r}")
    result = await fetch_provider_models(
        provider_id=provider_id,
        ollama_url=OLLAMA_URL,
        dmr_url=os.getenv("DMR_URL", "http://host-gateway:12434"),
    )
    return result


@app.post("/api/build", response_model=BuildResponse, tags=["Pipeline"])
async def build_agent(request: BuildRequest):
    """
    NLP-first pipeline: Ollama LLM analysis (with keyword fallback) → optional
    agent microservice scaffolding → returns full specification.
    """
    try:
        try:
            spec = await _builder.analyse_with_llm(request.job_description, request.model)
        except Exception:
            spec = _builder.analyse_fallback(request.job_description)

        scaffold_path: Optional[str] = None
        if request.scaffold:
            import re as _re
            agent_id = _re.sub(r"[^a-z0-9_]", "_", spec.get("agent_name", "agent").lower())
            result = scaffold_agent(
                agent_id=agent_id,
                agent_type=spec["agent_type"],
                domain=spec["domain"],
                system_prompt=spec["system_prompt"],
                tool_ids=spec["recommended_tools"],
                analysis=spec,
            )
            scaffold_path = result.get("path")

        # ── Intelligent model recommendation for the created agent ─────────────
        catalog = await discover_models(ollama_url=OLLAMA_URL, builder_model=request.model)
        model_rec = recommend_model(spec, catalog)
        builder_info = catalog["builder"]

        return BuildResponse(
            agent_name=spec.get("agent_name", "Agent"),
            agent_type=spec["agent_type"],
            domain=spec["domain"],
            sub_domain=spec.get("sub_domain", spec["domain"]),
            complexity_level=spec["complexity_level"],
            interaction_type=spec["interaction_type"],
            autonomy_level=spec["autonomy_level"],
            problem_type=spec["problem_type"],
            required_capabilities=spec.get("required_capabilities", []),
            recommended_tools=spec.get("recommended_tools", []),
            custom_tools_needed=spec.get("custom_tools_needed", []),
            rationale=spec.get("rationale", ""),
            system_prompt=spec["system_prompt"],
            analysis_source=spec.get("analysis_source", "llm"),
            scaffold_path=scaffold_path,
            recommended_model=model_rec,
            builder_model=builder_info,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/tools", tags=["Tools"])
def get_tools():
    """Return all available tools grouped by ecosystem."""
    return get_ecosystem_groups()


@app.get("/api/agents", tags=["Agents"])
def get_agents():
    """Return all scaffolded agents from the agents/ directory."""
    return {"agents": list_scaffolded_agents()}


# ---------------------------------------------------------------------------
# Docker / Ceagent agent builder endpoints
# ---------------------------------------------------------------------------

class DockerToolset(BaseModel):
    type: str = "builtin"        # "builtin" | "mcp"
    name: Optional[str] = None   # for builtin: shell | filesystem | todo | thinking
    reference: Optional[str] = None  # for mcp


class SingleDockerAgentRequest(BaseModel):
    agent_id: str
    model: str = "dmr/ai/gemma3"
    instruction: str
    toolsets: List[DockerToolset] = [DockerToolset(type="builtin", name="thinking")]
    port: int = 8301
    # Optional labels forwarded from the build pipeline
    agent_type: Optional[str] = None
    domain: Optional[str] = None
    complexity_level: Optional[int] = None
    interaction_type: Optional[str] = None
    autonomy_level: Optional[str] = None
    problem_type: Optional[str] = None


class DockerSubAgent(BaseModel):
    agent_id: str
    model: str = "dmr/ai/gemma3"
    description: str = ""
    instruction: str
    toolsets: List[DockerToolset] = [DockerToolset(type="builtin", name="thinking")]


class DockerRootAgent(BaseModel):
    model: str = "dmr/ai/gemma3"
    instruction: str = "You orchestrate specialised agents. Delegate tasks as needed."
    toolsets: List[DockerToolset] = [DockerToolset(type="builtin", name="thinking")]


class MultiDockerAgentRequest(BaseModel):
    agent_id: str
    root_agent: DockerRootAgent
    sub_agents: List[DockerSubAgent]
    port: int = 8401
    # Optional labels
    agent_type: Optional[str] = None
    domain: Optional[str] = None
    complexity_level: Optional[int] = None


class DockerAgentResponse(BaseModel):
    agent_id: str
    scaffold_type: str       # "single_docker" | "multi_docker"
    runtime: str             # "ceagent"
    path: str
    files_created: List[str]
    ceagent_yaml: str
    port: int
    sub_agents: List[str] = []


@app.post("/api/docker/single", response_model=DockerAgentResponse, tags=["Docker Agents"])
def create_docker_single(request: SingleDockerAgentRequest):
    """
    Scaffold a Ceagent v2 single-agent Docker project.

    Generates ceagent.yaml, Dockerfile, docker-compose.yml, .env.example,
    README.md, and agent.json under agents/<agent_id>/.
    """
    try:
        result = create_single_docker_agent(request.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return DockerAgentResponse(**result)


@app.post("/api/docker/multi", response_model=DockerAgentResponse, tags=["Docker Agents"])
def create_docker_multi(request: MultiDockerAgentRequest):
    """
    Scaffold a Ceagent v2 multi-agent orchestration Docker project.

    Creates a root orchestrator + one or more sub-agents, all wired in a
    single ceagent.yaml. Generates Dockerfile, docker-compose.yml, etc.
    """
    try:
        result = create_multi_docker_agent(request.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return DockerAgentResponse(**result)


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
