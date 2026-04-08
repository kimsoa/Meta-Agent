"""
Agent Scaffolder — writes each generated agent as a standalone microservice
in its own folder under ./agents/<agent_id>/

Folder structure per agent:
  agents/<agent_id>/
    agent.json          — metadata (type, domain, tools, system prompt)
    tools/              — one .py file per tool
      <tool_id>.py
    requirements.txt    — pip deps for the agent's tools
    run.py              — minimal FastAPI server wrapping the agent
    Dockerfile          — containerised deployment
    docker-compose.yml  — one-command launch
"""

import json
import textwrap
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from tool_registry import get_tool_code, PREDEFINED_TOOLS, GENERATED_TOOL_TEMPLATES

AGENTS_DIR = Path(__file__).parent / "agents"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def scaffold_agent(
    agent_id: str,
    agent_type: str,
    domain: str,
    system_prompt: str,
    tool_ids: List[str],
    analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create the full folder structure for one agent.
    Returns a summary dict with the agent_id and created paths.
    """
    agent_dir = AGENTS_DIR / agent_id
    tools_dir = agent_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)

    # --- Collect tool code and dependencies ---
    all_tool_meta = {**PREDEFINED_TOOLS, **GENERATED_TOOL_TEMPLATES}
    deps: List[str] = []
    written_tools: List[str] = []

    for tid in tool_ids:
        code = get_tool_code(tid)
        if not code:
            continue
        tool_file = tools_dir / f"{tid}.py"
        tool_file.write_text(f'"""Tool: {tid}"""\n\n' + code + "\n")
        written_tools.append(tid)
        tool_meta = all_tool_meta.get(tid, {})
        deps.extend(tool_meta.get("dependencies", []))

    # --- requirements.txt ---
    unique_deps = sorted(set(deps) | {"fastapi", "uvicorn[standard]", "httpx", "pydantic"})
    (agent_dir / "requirements.txt").write_text("\n".join(unique_deps) + "\n")

    # --- agent.json ---
    meta = {
        "agent_id": agent_id,
        "agent_type": agent_type,
        "domain": domain,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tools": written_tools,
        "analysis_summary": {
            "complexity_level": analysis.get("complexity_level"),
            "interaction_type": analysis.get("interaction_type"),
            "problem_type": analysis.get("problem_type"),
            "autonomy_level": analysis.get("autonomy_level"),
        },
    }
    (agent_dir / "agent.json").write_text(json.dumps(meta, indent=2) + "\n")

    # --- system_prompt.txt ---
    (agent_dir / "system_prompt.txt").write_text(system_prompt + "\n")

    # --- run.py — minimal FastAPI chat server ---
    run_py = textwrap.dedent(f"""\
        \"\"\"
        Auto-generated agent server for: {agent_id}
        Domain: {domain} | Type: {agent_type}

        Run:  uvicorn run:app --port 8100
        \"\"\"
        import importlib, json, os
        from pathlib import Path
        from typing import List
        import httpx
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from pydantic import BaseModel

        SYSTEM_PROMPT = Path(__file__).parent.joinpath('system_prompt.txt').read_text()
        OLLAMA_URL    = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        MODEL         = os.getenv('MODEL', 'gemma3:latest')
        AGENT_ID      = '{agent_id}'

        app = FastAPI(title=f'Agent: {agent_id}')
        app.add_middleware(CORSMiddleware, allow_origins=['*'],
                           allow_methods=['*'], allow_headers=['*'])

        class Message(BaseModel):
            role: str
            content: str

        class ChatRequest(BaseModel):
            messages: List[Message]
            model: str = MODEL

        @app.get('/health')
        def health():
            return {{'agent_id': AGENT_ID, 'status': 'ok'}}

        @app.post('/chat')
        async def chat(req: ChatRequest):
            payload = {{
                'model': req.model,
                'stream': False,
                'messages': [{{'role': 'system', 'content': SYSTEM_PROMPT}}]
                            + [{{'role': m.role, 'content': m.content}} for m in req.messages],
            }}
            async with httpx.AsyncClient(timeout=None) as client:
                r = await client.post(f'{{OLLAMA_URL}}/api/chat', json=payload)
                r.raise_for_status()
                return r.json()
    """)
    (agent_dir / "run.py").write_text(run_py)

    # --- Dockerfile ---
    dockerfile = textwrap.dedent(f"""\
        FROM python:3.12-slim
        WORKDIR /app
        COPY requirements.txt .
        RUN pip install --no-cache-dir -r requirements.txt
        COPY . .
        EXPOSE 8100
        ENV OLLAMA_URL=http://host.docker.internal:11434
        CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8100"]
    """)
    (agent_dir / "Dockerfile").write_text(dockerfile)

    # --- docker-compose.yml ---
    compose = textwrap.dedent(f"""\
        version: '3.9'
        services:
          {agent_id}:
            build: .
            ports:
              - "8100:8100"
            environment:
              OLLAMA_URL: http://host-gateway:11434
              MODEL: gemma3:latest
            extra_hosts:
              - "host-gateway:host-gateway"
    """)
    (agent_dir / "docker-compose.yml").write_text(compose)

    return {
        "agent_id": agent_id,
        "path": str(agent_dir),
        "tools": written_tools,
        "files": [
            "agent.json",
            "system_prompt.txt",
            "run.py",
            "requirements.txt",
            "Dockerfile",
            "docker-compose.yml",
        ] + [f"tools/{t}.py" for t in written_tools],
    }


# ---------------------------------------------------------------------------
# List / load existing scaffolded agents
# ---------------------------------------------------------------------------

def list_scaffolded_agents() -> List[Dict[str, Any]]:
    """Read agent.json from every subfolder of ./agents/."""
    if not AGENTS_DIR.exists():
        return []
    agents = []
    for folder in sorted(AGENTS_DIR.iterdir()):
        meta_file = folder / "agent.json"
        if meta_file.exists():
            try:
                agents.append(json.loads(meta_file.read_text()))
            except json.JSONDecodeError:
                pass
    return agents


def load_agent(agent_id: str) -> Dict[str, Any] | None:
    """Load metadata for a specific agent by ID."""
    meta_file = AGENTS_DIR / agent_id / "agent.json"
    if meta_file.exists():
        return json.loads(meta_file.read_text())
    return None


def load_system_prompt(agent_id: str) -> str | None:
    prompt_file = AGENTS_DIR / agent_id / "system_prompt.txt"
    if prompt_file.exists():
        return prompt_file.read_text()
    return None
