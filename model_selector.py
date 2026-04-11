"""
model_selector.py — Intelligent model discovery and recommendation engine.

Discovers which inference backends are available (local Ollama + external
providers configured via API-key ENV vars) and recommends the best model
for each generated agent based on its complexity, type, and autonomy level.

Complexity → required model tier:
  1  tiny   (≤2B params)  — simple_reflex, automated, ignorable problems
  2  small  (3–9B params) — model_based, low-medium autonomy
  3  medium (10–22B)      — goal_based, conversational, medium autonomy
  4  large  (23–42B)      — utility_based, hybrid, high autonomy
  5  xlarge (42B+)        — irrecoverable, mission-critical, max capability

Discovery order (preference):
  1. Local Ollama — always checked first (free, private, no latency)
  2. External API providers — surfaced only when API key ENV var is set
"""

import os
import re
from typing import Any, Dict, List, Optional, NamedTuple

import httpx


# ─── Known model sizes ────────────────────────────────────────────────────────
# Maps common Ollama tags → approximate parameter count in billions.
# Used when the tag does not contain an explicit size like ':8b'.

_KNOWN_SIZES: Dict[str, float] = {
    # Gemma family
    "gemma3":              12.0,
    "gemma3:latest":       12.0,
    "gemma3:1b":            1.0,
    "gemma3:4b":            4.0,
    "gemma3:12b":          12.0,
    "gemma3:27b":          27.0,
    "gemma2":               9.0,
    "gemma2:latest":        9.0,
    "gemma":                7.0,
    "gemma:latest":         7.0,
    # Mistral family
    "mistral":              7.0,
    "mistral:latest":       7.0,
    "mistral-nemo":        12.0,
    "mistral-nemo:latest": 12.0,
    "mixtral":             46.7,
    "mixtral:latest":      46.7,
    # Phi family
    "phi3":                 3.8,
    "phi3:latest":          3.8,
    "phi3:mini":            3.8,
    "phi3:medium":         14.0,
    "phi4":                14.0,
    "phi4:latest":         14.0,
    # LLaMA 3.x family
    "llama3":               8.0,
    "llama3:latest":        8.0,
    "llama3.1":             8.0,
    "llama3.1:latest":      8.0,
    "llama3.2":             3.0,
    "llama3.2:latest":      3.0,
    "llama3.3":            70.0,
    "llama3.3:latest":     70.0,
    # DeepSeek
    "deepseek-r1":         32.0,
    "deepseek-r1:latest":  32.0,
    "deepseek-v2":         16.0,
    "deepseek-v2:latest":  16.0,
    "deepseek-coder":       7.0,
    "deepseek-coder:latest":7.0,
    # Qwen family
    "qwen2":                7.0,
    "qwen2:latest":         7.0,
    "qwen2.5":              7.0,
    "qwen2.5:latest":       7.0,
    "qwen2.5-coder":        7.0,
    "qwen2.5-coder:latest": 7.0,
    # Other
    "command-r":           35.0,
    "command-r:latest":    35.0,
    "solar":               10.7,
    "solar:latest":        10.7,
    "vicuna":              13.0,
    "vicuna:latest":       13.0,
    "codellama":           13.0,
    "codellama:latest":    13.0,
    "yi":                   6.0,
    "yi:latest":            6.0,
    "starling-lm":          7.0,
}

_EMBEDDING_RE = re.compile(r"embed|bert|e5-|bge-|nomic|minilm|rerank", re.I)


def _extract_size_b(model_name: str) -> float:
    """Infer parameter count (billions) from a model's Ollama tag."""
    # Direct lookup
    if model_name in _KNOWN_SIZES:
        return _KNOWN_SIZES[model_name]
    # Explicit size in tag e.g. 'llama3.1:8b', 'qwen2.5:32b', 'gemma3:1.5b'
    m = re.search(r":(\d+(?:\.\d+)?)b", model_name, re.I)
    if m:
        return float(m.group(1))
    # Basename lookup (strip tag suffix)
    base = model_name.split(":")[0]
    if base in _KNOWN_SIZES:
        return _KNOWN_SIZES[base]
    return 7.0  # safe default — treat as mid-size


def _size_to_tier(size_b: float) -> int:
    """Map model size → capability tier 1–5."""
    if size_b <= 2.5:
        return 1
    if size_b <= 9.0:
        return 2
    if size_b <= 22.0:
        return 3
    if size_b <= 42.0:
        return 4
    return 5


# ─── External provider catalogue ──────────────────────────────────────────────

class _ExtEntry(NamedTuple):
    provider_id: str
    provider_label: str
    min_tier: int       # minimum complexity tier this model handles well
    max_tier: int       # maximum complexity tier this model handles well
    model_id: str       # canonical model identifier for the provider's API
    env_var: str        # ENV var whose presence signals the key is configured
    reason: str         # human-readable explanation for recommendation


_EXTERNAL_CATALOGUE: List[_ExtEntry] = [
    # ── OpenAI ────────────────────────────────────────────────────────────────
    _ExtEntry("openai", "OpenAI",     1, 3, "gpt-4o-mini",
              "OPENAI_API_KEY",
              "Fast, cost-effective — strong general reasoning for low-to-medium complexity agents"),
    _ExtEntry("openai", "OpenAI",     3, 5, "gpt-4o",
              "OPENAI_API_KEY",
              "Top-tier reasoning, tool use, and long-context for complex mission-critical agents"),

    # ── Anthropic ─────────────────────────────────────────────────────────────
    _ExtEntry("anthropic", "Anthropic", 1, 3, "claude-3-haiku-20240307",
              "ANTHROPIC_API_KEY",
              "Ultra-fast Claude Haiku — excellent for high-throughput, responsive agents"),
    _ExtEntry("anthropic", "Anthropic", 3, 5, "claude-3-5-sonnet-20241022",
              "ANTHROPIC_API_KEY",
              "Claude Sonnet — nuanced reasoning, large 200K context, strong agentic tool-use"),

    # ── Groq (LPU inference — very fast) ─────────────────────────────────────
    _ExtEntry("groq", "Groq (LPU)",  1, 3, "llama3-8b-8192",
              "GROQ_API_KEY",
              "LLaMA 3 8B on Groq LPUs — sub-100ms responses, free tier available"),
    _ExtEntry("groq", "Groq (LPU)",  3, 5, "llama-3.1-70b-versatile",
              "GROQ_API_KEY",
              "LLaMA 3.1 70B on Groq LPUs — near-GPT-4 quality at very high throughput"),

    # ── Mistral AI ────────────────────────────────────────────────────────────
    _ExtEntry("mistral", "Mistral AI", 1, 3, "mistral-small-latest",
              "MISTRAL_API_KEY",
              "Mistral Small — efficient, GDPR-compliant European model with strong EU language support"),
    _ExtEntry("mistral", "Mistral AI", 3, 5, "mistral-large-latest",
              "MISTRAL_API_KEY",
              "Mistral Large — top-tier reasoning, multilingual, strong coding capability"),

    # ── Together AI ───────────────────────────────────────────────────────────
    _ExtEntry("together", "Together AI", 3, 5,
              "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
              "TOGETHER_API_KEY",
              "Open-source LLaMA 70B via Together — cost-effective alternative to GPT-4 class"),

    # ── Google AI (Gemini) ────────────────────────────────────────────────────
    _ExtEntry("google", "Google AI", 1, 3, "gemini-1.5-flash",
              "GOOGLE_API_KEY",
              "Gemini Flash — 1M token context window, multimodal, very fast inference"),
    _ExtEntry("google", "Google AI", 3, 5, "gemini-1.5-pro",
              "GOOGLE_API_KEY",
              "Gemini Pro — 1M context, sophisticated multi-step reasoning, grounding support"),

    # ── Cohere ────────────────────────────────────────────────────────────────
    _ExtEntry("cohere", "Cohere", 2, 4, "command-r",
              "COHERE_API_KEY",
              "Command-R — purpose-built for RAG and agentic tasks with grounded citations"),
    _ExtEntry("cohere", "Cohere", 4, 5, "command-r-plus",
              "COHERE_API_KEY",
              "Command-R+ — enterprise Cohere flagship with strong tool-use and reasoning"),
]


# ─── Model candidate dataclass ────────────────────────────────────────────────

class ModelCandidate:
    """A discovered model (local or external) with tier and metadata."""

    def __init__(
        self,
        model_id: str,
        provider: str,
        provider_label: str,
        tier: int,
        reason: str,
        is_local: bool = True,
        requires_key: Optional[str] = None,
        min_tier: int = 1,
        max_tier: int = 5,
    ):
        self.model_id = model_id
        self.provider = provider
        self.provider_label = provider_label
        self.tier = tier
        self.min_tier = min_tier
        self.max_tier = max_tier
        self.reason = reason
        self.is_local = is_local
        self.requires_key = requires_key

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "provider_label": self.provider_label,
            "tier": self.tier,
            "reason": self.reason,
            "is_local": self.is_local,
            "requires_key": self.requires_key,
        }


# ─── Discovery ────────────────────────────────────────────────────────────────

async def discover_models(
    ollama_url: str = "http://localhost:11434",
    builder_model: str = "gemma3:latest",
) -> Dict[str, Any]:
    """
    Probe Ollama + env vars and return a full model catalog.

    Returns:
      {
        "builder": {model_id, provider, provider_label, tier, reason},
        "local": [ModelCandidate.to_dict(), ...],
        "external": [ModelCandidate.to_dict(), ...],
        "configured_providers": ["openai", "groq", ...],
      }
    """
    local: List[ModelCandidate] = []
    external: List[ModelCandidate] = []

    # ── 1. Local Ollama ───────────────────────────────────────────────────────
    ollama_reachable = False
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{ollama_url}/api/tags")
            resp.raise_for_status()
            raw_models = resp.json().get("models", [])
            ollama_reachable = True
    except Exception:
        raw_models = []

    for m in raw_models:
        name = m["name"]
        if _EMBEDDING_RE.search(name):
            continue  # skip embedding models
        size_b = _extract_size_b(name)
        tier = _size_to_tier(size_b)
        local.append(ModelCandidate(
            model_id=name,
            provider="ollama_local",
            provider_label="Local Ollama",
            tier=tier,
            reason=f"~{size_b:.0f}B parameter model — runs locally, free, fully private",
            is_local=True,
            min_tier=max(1, tier - 1),
            max_tier=min(5, tier + 1),
        ))

    # ── 2. External providers ─────────────────────────────────────────────────
    configured_providers: List[str] = []
    for entry in _EXTERNAL_CATALOGUE:
        if os.getenv(entry.env_var):
            if entry.provider_id not in configured_providers:
                configured_providers.append(entry.provider_id)
            mid_tier = (entry.min_tier + entry.max_tier) // 2
            external.append(ModelCandidate(
                model_id=entry.model_id,
                provider=entry.provider_id,
                provider_label=entry.provider_label,
                tier=mid_tier,
                min_tier=entry.min_tier,
                max_tier=entry.max_tier,
                reason=entry.reason,
                is_local=False,
                requires_key=entry.env_var,
            ))

    # ── Builder metadata ──────────────────────────────────────────────────────
    builder_size = _extract_size_b(builder_model)
    builder_tier = _size_to_tier(builder_size)
    builder_info = {
        "model_id": builder_model,
        "provider": "ollama_local" if ollama_reachable else "unknown",
        "provider_label": "Local Ollama" if ollama_reachable else "Unknown",
        "tier": builder_tier,
        "ollama_reachable": ollama_reachable,
        "reason": (
            f"Meta-Agent Builder — analyses job descriptions and generates agent specs. "
            f"Uses {builder_model} (~{builder_size:.0f}B, tier {builder_tier}) "
            f"via Ollama at {ollama_url}."
        ),
    }

    return {
        "builder": builder_info,
        "local": [c.to_dict() for c in local],
        "external": [c.to_dict() for c in external],
        "configured_providers": configured_providers,
        "ollama_reachable": ollama_reachable,
    }


# ─── Complexity → required tier ───────────────────────────────────────────────

def _required_tier(spec: Dict[str, Any]) -> int:
    """
    Derive minimum model tier needed for this agent spec.
    Accounts for complexity, agent type, autonomy, and problem type.
    """
    complexity = max(1, min(5, int(spec.get("complexity_level", 3))))
    agent_type = spec.get("agent_type", "conversational")
    autonomy = spec.get("autonomy_level", "medium")
    problem_type = spec.get("problem_type", "recoverable")

    tier = complexity  # baseline

    # Autonomous / high-stakes agents need stronger models
    if autonomy == "high" and tier < 3:
        tier = 3
    if problem_type == "irrecoverable" and tier < 4:
        tier = 4

    # Conversational agents need at least small (tier 2) for coherent dialogue
    if agent_type == "conversational" and tier < 2:
        tier = 2

    # Utility-based (optimisation) needs at least tier 3
    if agent_type == "utility_based" and tier < 3:
        tier = 3

    return min(tier, 5)


# ─── Recommendation engine ────────────────────────────────────────────────────

def recommend_model(
    spec: Dict[str, Any],
    catalog: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Given an agent spec and the discovered model catalog, return the best
    model recommendation plus alternatives.

    Strategy:
      1. Prefer local Ollama models that meet the required tier (free + private)
      2. If no local model meets the tier, escalate to external providers
      3. Always list top-3 external alternatives if any are configured
    """
    req_tier = _required_tier(spec)
    complexity = int(spec.get("complexity_level", 3))
    agent_type = spec.get("agent_type", "conversational")

    # Reconstruct ModelCandidate objects from dict for scoring
    local_candidates: List[ModelCandidate] = []
    for d in catalog.get("local", []):
        local_candidates.append(ModelCandidate(
            model_id=d["model_id"],
            provider=d["provider"],
            provider_label=d["provider_label"],
            tier=d["tier"],
            reason=d["reason"],
            is_local=True,
        ))

    external_candidates: List[ModelCandidate] = []
    for d in catalog.get("external", []):
        external_candidates.append(ModelCandidate(
            model_id=d["model_id"],
            provider=d["provider"],
            provider_label=d["provider_label"],
            tier=d.get("tier", 3),
            min_tier=d.get("min_tier", 1),
            max_tier=d.get("max_tier", 5),
            reason=d["reason"],
            is_local=False,
            requires_key=d.get("requires_key"),
        ))

    # ── Score local models ────────────────────────────────────────────────────
    def _local_score(c: ModelCandidate) -> float:
        diff = c.tier - req_tier
        if diff < 0:
            return diff * 3          # under-powered: strong penalty
        return -diff * 0.4           # over-powered: slight penalty (wasteful but works)

    eligible_local = [c for c in local_candidates if c.tier >= req_tier]
    if not eligible_local:
        # No local model strong enough — use the biggest available as fallback
        eligible_local = sorted(local_candidates, key=lambda c: c.tier, reverse=True)

    best_local = max(eligible_local, key=_local_score) if eligible_local else None

    # ── Score external models that cover the required tier ────────────────────
    eligible_external = [
        c for c in external_candidates
        if c.min_tier <= req_tier <= c.max_tier
    ]

    # ── Determine primary recommendation ──────────────────────────────────────
    local_is_sufficient = (
        best_local is not None and best_local.tier >= req_tier
    )

    if local_is_sufficient:
        primary = best_local
        provider_note = "Local model — fully private, no API cost."
        if eligible_external:
            provider_note += (
                f" External alternatives available via "
                f"{', '.join(set(c.provider_label for c in eligible_external[:2]))}."
            )
        reason = (
            f"Complexity-{complexity} {agent_type.replace('_', ' ')} agent "
            f"requires tier {req_tier}. {primary.model_id} (tier {primary.tier}) "
            f"meets this threshold. {provider_note}"
        )
        warning = None

    elif best_local is not None:
        # Local available but under-powered
        primary = best_local
        warning = (
            f"Your strongest local model ({best_local.model_id}, tier {best_local.tier}) "
            f"is below the recommended tier {req_tier} for this agent. "
            f"Consider pulling a larger model or using an external provider."
        )
        reason = (
            f"Best available local option for complexity-{complexity}. "
            f"Tier {primary.tier} vs required tier {req_tier} — "
            f"performance may be limited. {primary.reason}."
        )
    elif eligible_external:
        # No local models at all — go external
        primary = eligible_external[0]
        warning = "No local Ollama models found. Using external provider."
        reason = (
            f"No local models available. "
            f"{primary.provider_label} → {primary.model_id} "
            f"recommended for complexity-{complexity} agent. {primary.reason}."
        )
    else:
        # Nothing available anywhere
        return {
            "model_id": "gemma3:latest",
            "provider": "ollama_local",
            "provider_label": "Local Ollama",
            "tier": 3,
            "required_tier": req_tier,
            "reason": (
                "No models discovered. Pull a model with: ollama pull gemma3  "
                "or set an API key ENV var for an external provider."
            ),
            "warning": "No models available locally or via external providers.",
            "is_local": True,
            "alternatives": [],
        }

    # ── Build alternatives list ────────────────────────────────────────────────
    alternatives = []
    # Add top external options not already selected as primary
    for c in eligible_external:
        if c.model_id == primary.model_id:
            continue
        if len(alternatives) >= 3:
            break
        alternatives.append({
            "model_id": c.model_id,
            "provider": c.provider,
            "provider_label": c.provider_label,
            "reason": c.reason,
            "is_local": False,
        })

    # Also add other good local models as alternatives (only if at least as capable as primary)
    for c in sorted(eligible_local, key=_local_score, reverse=True):
        if c.model_id == primary.model_id:
            continue
        if c.tier < primary.tier:
            continue  # never suggest weaker models as alternatives
        if len(alternatives) >= 4:
            break
        alternatives.append({
            "model_id": c.model_id,
            "provider": c.provider,
            "provider_label": c.provider_label,
            "reason": c.reason,
            "is_local": True,
        })

    result: Dict[str, Any] = {
        "model_id": primary.model_id,
        "provider": primary.provider,
        "provider_label": primary.provider_label,
        "tier": primary.tier,
        "required_tier": req_tier,
        "reason": reason,
        "is_local": primary.is_local,
        "alternatives": alternatives,
    }
    if "warning" in locals() and warning:
        result["warning"] = warning

    return result


# ─── Provider definitions ─────────────────────────────────────────────────────

PROVIDER_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "ollama_local": {
        "id":               "ollama_local",
        "label":            "Local Ollama",
        "type":             "local",
        "description":      "Locally running Ollama — free, private, no API costs",
        "key_env_var":      None,
        "models_fetchable": True,
    },
    "docker_model_runner": {
        "id":               "docker_model_runner",
        "label":            "Docker Model Runner",
        "type":             "local",
        "description":      "Docker-native model runner (dmr/ prefix models)",
        "key_env_var":      None,
        "models_fetchable": True,
    },
    "openai": {
        "id":               "openai",
        "label":            "OpenAI",
        "type":             "cloud",
        "description":      "GPT-4o, GPT-4o-mini, o1, o3-mini",
        "key_env_var":      "OPENAI_API_KEY",
        "models_fetchable": True,
    },
    "anthropic": {
        "id":               "anthropic",
        "label":            "Anthropic",
        "type":             "cloud",
        "description":      "Claude 3.5 Sonnet, Haiku — strong reasoning & long context",
        "key_env_var":      "ANTHROPIC_API_KEY",
        "models_fetchable": False,
    },
    "groq": {
        "id":               "groq",
        "label":            "Groq",
        "type":             "cloud",
        "description":      "Ultra-fast LPU inference — LLaMA, Mixtral, Gemma models",
        "key_env_var":      "GROQ_API_KEY",
        "models_fetchable": True,
    },
    "mistral": {
        "id":               "mistral",
        "label":            "Mistral AI",
        "type":             "cloud",
        "description":      "Mistral Small, Large — GDPR-compliant European models",
        "key_env_var":      "MISTRAL_API_KEY",
        "models_fetchable": True,
    },
    "google": {
        "id":               "google",
        "label":            "Google AI",
        "type":             "cloud",
        "description":      "Gemini 1.5 Flash & Pro — 1M token context, multimodal",
        "key_env_var":      "GOOGLE_API_KEY",
        "models_fetchable": True,
    },
    "together": {
        "id":               "together",
        "label":            "Together AI",
        "type":             "cloud",
        "description":      "Open-source LLaMA, Mixtral via Together's API",
        "key_env_var":      "TOGETHER_API_KEY",
        "models_fetchable": True,
    },
    "cohere": {
        "id":               "cohere",
        "label":            "Cohere",
        "type":             "cloud",
        "description":      "Command-R and R+ — built for RAG and agentic tasks",
        "key_env_var":      "COHERE_API_KEY",
        "models_fetchable": False,
    },
}


async def get_providers_status(
    ollama_url: str = "http://localhost:11434",
    dmr_url: str = "http://host-gateway:12434",
) -> List[Dict[str, Any]]:
    """Return all provider definitions enriched with live configured/reachable status."""
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(f"{ollama_url}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        pass

    dmr_ok = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{dmr_url}/v1/models")
            dmr_ok = r.status_code == 200
    except Exception:
        pass

    result = []
    for pid, defn in PROVIDER_DEFINITIONS.items():
        if pid == "ollama_local":
            configured = ollama_ok
        elif pid == "docker_model_runner":
            configured = dmr_ok
        else:
            configured = bool(os.getenv(defn["key_env_var"])) if defn["key_env_var"] else False
        result.append({**defn, "configured": configured})
    return result


async def fetch_provider_models(
    provider_id: str,
    ollama_url: str = "http://localhost:11434",
    dmr_url: str = "http://host-gateway:12434",
) -> Dict[str, Any]:
    """
    Fetch the live model list from a specific provider.

    - Local providers (ollama_local, docker_model_runner): calls their API directly.
    - Cloud providers with a /models endpoint (openai, groq, mistral, google, together):
      fetches live when the API key ENV var is set.
    - Providers without a list endpoint (anthropic, cohere) or unconfigured keys:
      falls back to the curated _EXTERNAL_CATALOGUE entries for that provider.
    """
    defn = PROVIDER_DEFINITIONS.get(provider_id)
    if not defn:
        raise ValueError(f"Unknown provider: {provider_id}")

    api_key: Optional[str] = os.getenv(defn["key_env_var"]) if defn["key_env_var"] else None
    models: List[Dict[str, Any]] = []
    fetch_error: Optional[str] = None
    fetched_live = False

    try:
        if provider_id == "ollama_local":
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(f"{ollama_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
            for m in data.get("models", []):
                name = m["name"]
                if _EMBEDDING_RE.search(name):
                    continue
                size_b = _extract_size_b(name)
                models.append({
                    "id": name, "name": name,
                    "tier": _size_to_tier(size_b), "size_b": round(size_b, 1),
                    "description": f"~{size_b:.0f}B — local, free, private",
                    "source": "installed", "is_local": True,
                })
            fetched_live = True

        elif provider_id == "docker_model_runner":
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(f"{dmr_url}/v1/models")
                resp.raise_for_status()
                data = resp.json()
            for m in data.get("data", []):
                raw_id = m.get("id") or m.get("name", "")
                model_id = raw_id if raw_id.startswith("dmr/") else f"dmr/{raw_id}"
                models.append({
                    "id": model_id, "name": model_id, "tier": 2,
                    "description": "Docker Model Runner model",
                    "source": "installed", "is_local": True,
                })
            fetched_live = True

        elif provider_id == "openai" and api_key:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
            chat_pfx = ("gpt-3.5", "gpt-4", "o1", "o3", "chatgpt")
            for m in data.get("data", []):
                mid = m["id"]
                if any(mid.startswith(p) for p in chat_pfx):
                    tier = 4 if any(k in mid for k in ("gpt-4", "o1", "o3")) else 2
                    models.append({
                        "id": mid, "name": mid, "tier": tier,
                        "description": "OpenAI chat model",
                        "source": "api", "is_local": False,
                    })
            models.sort(key=lambda x: x["id"])
            fetched_live = True

        elif provider_id == "groq" and api_key:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
            for m in data.get("data", []):
                mid = m["id"]
                tier = 4 if any(k in mid for k in ("70b", "8x7b", "405b")) else 2
                models.append({
                    "id": mid, "name": mid, "tier": tier,
                    "description": "Groq LPU inference model",
                    "source": "api", "is_local": False,
                })
            models.sort(key=lambda x: x["id"])
            fetched_live = True

        elif provider_id == "mistral" and api_key:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.mistral.ai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
            for m in data.get("data", []):
                mid = m["id"]
                if "embed" not in mid:
                    tier = 4 if any(k in mid for k in ("large", "medium")) else 2
                    models.append({
                        "id": mid, "name": mid, "tier": tier,
                        "description": m.get("description", "Mistral AI model"),
                        "source": "api", "is_local": False,
                    })
            models.sort(key=lambda x: x["id"])
            fetched_live = True

        elif provider_id == "google" and api_key:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
                )
                resp.raise_for_status()
                data = resp.json()
            for m in data.get("models", []):
                name = m.get("name", "").replace("models/", "")
                if "gemini" in name and "embed" not in name and "aqa" not in name:
                    tier = 4 if "pro" in name else 2
                    models.append({
                        "id": name, "name": name, "tier": tier,
                        "description": m.get("displayName", "Google AI model"),
                        "source": "api", "is_local": False,
                    })
            models.sort(key=lambda x: x["id"])
            fetched_live = True

        elif provider_id == "together" and api_key:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.together.xyz/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
            items = data if isinstance(data, list) else data.get("data", [])
            for m in items:
                mid = m.get("id") or m.get("name", "")
                if mid and m.get("type", "chat") in ("chat", "language", ""):
                    models.append({
                        "id": mid, "name": m.get("display_name", mid), "tier": 3,
                        "description": m.get("description", "Together AI model"),
                        "source": "api", "is_local": False,
                    })
            models.sort(key=lambda x: x["id"])
            fetched_live = True

    except Exception as exc:
        fetch_error = str(exc)

    # Fall back to curated catalogue when live fetch failed or was skipped
    if not models:
        for entry in _EXTERNAL_CATALOGUE:
            if entry.provider_id == provider_id:
                models.append({
                    "id": entry.model_id, "name": entry.model_id,
                    "tier": (entry.min_tier + entry.max_tier) // 2,
                    "description": entry.reason,
                    "source": "catalog", "is_local": False,
                })

    return {
        "provider_id": provider_id,
        "provider_label": defn["label"],
        "models": models,
        "fetched_live": fetched_live,
        "error": fetch_error,
    }
