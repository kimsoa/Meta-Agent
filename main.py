# Meta-Agent Builder — NLP-first analysis engine
#
# Pipeline:
#   1. PRIMARY  — async call to Ollama with structured prompt → parse JSON
#   2. FALLBACK — keyword/rule heuristics (only when Ollama is unreachable)

import json
import re
import textwrap
from typing import Any, Dict, List, Tuple

import httpx

OLLAMA_URL_DEFAULT = "http://localhost:11434"

# ─────────────────────────────────────────────────────────────────────────────
# Prompt sent to Ollama — must return a single JSON object, nothing else
# ─────────────────────────────────────────────────────────────────────────────

ANALYSIS_PROMPT = textwrap.dedent("""\
You are an expert AI agent architect. Read the job description and produce a
precise structured specification for an AI agent that fulfils it.

Return ONLY a single valid JSON object — no markdown fences, no prose, no
commentary. The object must conform to this schema exactly:

{
  "domain": "<primary domain slug, e.g. ecommerce, coding_assistant, healthcare, finance, data_analysis>",
  "sub_domain": "<specific area, e.g. post_purchase_support, code_review_automation>",
  "agent_type": "<simple_reflex | model_based | goal_based | utility_based | conversational | automated>",
  "complexity_level": <integer 1-5>,
  "interaction_type": "<conversational | automated | hybrid>",
  "problem_type": "<ignorable | recoverable | irrecoverable>",
  "autonomy_level": "<low | medium | high>",
  "required_capabilities": ["<capability strings>"],
  "recommended_tools": [
    "<slug — only from: gmail, google_calendar, google_drive, outlook_email, teams,
      sharepoint, web_search, database_query, http_request, file_operations,
      escalate_to_human, linter, code_formatter, test_runner, code_executor,
      pdf_reader, sentiment_analyzer, order_lookup, ticket_creator>"
  ],
  "custom_tools_needed": [
    {"name": "<short name>", "description": "<one sentence>", "reason": "<why needed>"}
  ],
  "rationale": "<2-3 sentences explaining why these choices>",
  "agent_name": "<short memorable name>",
  "system_prompt": "<complete production-ready system prompt for this agent>"
}

Rules:
- domain AND sub_domain must be precise. Never just write 'customer_service' —
  distinguish post-purchase vs pre-sales vs technical troubleshooting vs billing.
- recommended_tools must only contain slugs from the list above.
- system_prompt must be comprehensive: role, capabilities, constraints, tone.
- complexity_level is about task difficulty, not technology.

Job description:
\"\"\"
{job_description}
\"\"\"
""")

AGENT_TYPES = {
    "simple_reflex": {
        "description": "Fast reactive agent with no memory, responds to current input only",
        "use_cases": ["real-time monitoring", "threshold-based alerts", "simple automation"],
        "characteristics": ["fast execution", "no memory", "rule-based decisions"],
        "complexity": 1,
    },
    "model_based": {
        "description": "Agent with internal world model and memory of past states",
        "use_cases": ["data analysis", "tracking systems", "state management"],
        "characteristics": ["internal model", "memory", "state tracking"],
        "complexity": 2,
    },
    "goal_based": {
        "description": "Agent that works towards explicit goals with planning",
        "use_cases": ["project management", "task completion", "strategic planning"],
        "characteristics": ["goal-oriented", "planning", "adaptation"],
        "complexity": 3,
    },
    "utility_based": {
        "description": "Agent that optimises for utility/happiness metrics",
        "use_cases": ["optimisation tasks", "resource allocation", "decision making"],
        "characteristics": ["utility evaluation", "preference ranking", "optimisation"],
        "complexity": 4,
    },
    "conversational": {
        "description": "Agent focused on natural language interaction and dialogue",
        "use_cases": ["customer service", "assistance", "information retrieval"],
        "characteristics": ["dialogue management", "context retention", "user interaction"],
        "complexity": 3,
    },
    "automated": {
        "description": "Agent that runs background tasks without human intervention",
        "use_cases": ["data processing", "system monitoring", "batch operations"],
        "characteristics": ["autonomous operation", "scheduled tasks", "minimal interaction"],
        "complexity": 2,
    },
}

PROBLEM_TYPES = {
    "ignorable": {
        "description": "Problems where some steps can be skipped without impact",
        "agent_implications": ["simpler heuristics", "lower computational budget"],
    },
    "recoverable": {
        "description": "Problems where mistakes can be undone or corrected",
        "agent_implications": ["rollback mechanisms", "exploratory planning"],
    },
    "irrecoverable": {
        "description": "Problems where actions are permanent and mistakes costly",
        "agent_implications": ["strong safety checks", "utility-based evaluation"],
    },
}


class MetaAgentBuilder:
    """
    Analyses a job description using Ollama NLP (primary) or keyword
    heuristics (fallback) and produces a complete agent specification.
    """

    def __init__(self, ollama_url: str = OLLAMA_URL_DEFAULT):
        self.ollama_url = ollama_url
        self.agent_types = AGENT_TYPES
        self.problem_types = PROBLEM_TYPES

    # ── PRIMARY: LLM NLP analysis ─────────────────────────────────────────────

    async def analyse_with_llm(
        self, job_description: str, model: str = "gemma3:latest"
    ) -> Dict[str, Any]:
        """
        Call Ollama → structured JSON spec.
        Raises ValueError on bad JSON, httpx errors on network failure.
        """
        prompt = ANALYSIS_PROMPT.format(job_description=job_description)
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a precise JSON-only API. "
                        "Return ONLY valid JSON — no markdown fences, no commentary."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "options": {"temperature": 0.2},
        }
        timeout = httpx.Timeout(connect=10.0, read=None, write=None, pool=None)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{self.ollama_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        raw: str = data["message"]["content"].strip()
        # Strip markdown fences in case the model ignored instructions
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            spec = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                spec = json.loads(match.group())
            else:
                raise ValueError(f"LLM did not return valid JSON:\n{raw[:400]}")

        return self._normalise_spec(spec)

    # ── FALLBACK: keyword heuristics ─────────────────────────────────────────

    def analyse_fallback(self, job_description: str) -> Dict[str, Any]:
        """Pure keyword heuristics — used only when Ollama is unreachable."""
        from tool_registry import get_tools_for_domain

        text = job_description.lower()
        domain = self._kw_domain(text)
        complexity = self._kw_complexity(text)
        interaction = self._kw_interaction(text)
        problem_type = self._kw_problem_type(text)
        autonomy = self._kw_autonomy(text)
        caps = self._kw_capabilities(text)
        tools = get_tools_for_domain(domain)
        agent_type = self._kw_agent_type(complexity, interaction, problem_type, autonomy, caps)

        spec: Dict[str, Any] = {
            "domain": domain,
            "sub_domain": domain,
            "agent_type": agent_type,
            "complexity_level": complexity,
            "interaction_type": interaction,
            "problem_type": problem_type,
            "autonomy_level": autonomy,
            "required_capabilities": caps,
            "recommended_tools": tools,
            "custom_tools_needed": [],
            "rationale": (
                f"Keyword heuristics selected '{agent_type}' (Ollama unavailable). "
                f"Domain: {domain}, complexity {complexity}/5."
            ),
            "agent_name": f"{domain.replace('_', ' ').title()} Agent",
            "analysis_source": "keyword_fallback",
        }
        spec["system_prompt"] = self._build_system_prompt(spec)
        return spec

    # ── Normalisation ─────────────────────────────────────────────────────────

    def _normalise_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Validate + fill any holes in LLM output."""
        from tool_registry import get_tools_for_domain, PREDEFINED_TOOLS, GENERATED_TOOL_TEMPLATES

        all_tool_ids = set({**PREDEFINED_TOOLS, **GENERATED_TOOL_TEMPLATES}.keys())

        if spec.get("agent_type") not in AGENT_TYPES:
            spec["agent_type"] = "conversational"
        if spec.get("problem_type") not in PROBLEM_TYPES:
            spec["problem_type"] = "recoverable"
        try:
            spec["complexity_level"] = max(1, min(5, int(spec.get("complexity_level", 3))))
        except (TypeError, ValueError):
            spec["complexity_level"] = 3
        if spec.get("interaction_type") not in ("conversational", "automated", "hybrid"):
            spec["interaction_type"] = "conversational"
        if spec.get("autonomy_level") not in ("low", "medium", "high"):
            spec["autonomy_level"] = "medium"

        tools = [t for t in (spec.get("recommended_tools") or []) if t in all_tool_ids]
        if len(tools) < 2:
            tools += [t for t in get_tools_for_domain(spec.get("domain", "general")) if t not in tools]
        spec["recommended_tools"] = tools

        if not isinstance(spec.get("custom_tools_needed"), list):
            spec["custom_tools_needed"] = []
        if not isinstance(spec.get("required_capabilities"), list):
            spec["required_capabilities"] = ["communication"]
        if not spec.get("agent_name"):
            spec["agent_name"] = f"{spec.get('domain', 'general').replace('_', ' ').title()} Agent"
        if not spec.get("system_prompt"):
            spec["system_prompt"] = self._build_system_prompt(spec)

        spec["analysis_source"] = "llm"
        return spec

    def _build_system_prompt(self, spec: Dict[str, Any]) -> str:
        agent_type = spec.get("agent_type", "conversational")
        domain = spec.get("domain", "general")
        autonomy = spec.get("autonomy_level", "medium")
        problem_type = spec.get("problem_type", "recoverable")
        caps = spec.get("required_capabilities", [])
        tools = spec.get("recommended_tools", [])
        safety = {
            "irrecoverable": "Always confirm before permanent actions. Log every operation.",
            "recoverable": "Save checkpoints. Allow rollback on multi-step operations.",
            "ignorable": "Standard input validation and error handling apply.",
        }.get(problem_type, "Standard error handling applies.")
        cap_lines = "\n".join(f"- {c.replace('_', ' ').title()}" for c in caps) or "- Communication"
        tool_lines = "\n".join(f"- {t.replace('_', ' ').title()}" for t in tools) or "- None configured"
        return textwrap.dedent(f"""\
            # {agent_type.replace('_', ' ').title()} Agent — {domain.replace('_', ' ').title()}

            ## Role
            You are a specialised AI agent for {domain.replace('_', ' ')} tasks.
            Operating with {autonomy} autonomy using a {agent_type.replace('_', ' ')} approach.

            ## Capabilities
            {cap_lines}

            ## Available Tools
            {tool_lines}

            ## Safety
            {safety}

            ## Guidelines
            - Maintain context and coherence across turns.
            - Ask for clarification when requirements are ambiguous.
            - Prioritise user safety and data security at all times.
            - Explain reasoning when making consequential decisions.
        """).strip()

    # ── Keyword heuristic helpers ─────────────────────────────────────────────

    def _kw_domain(self, text: str) -> str:
        domains = {
            "customer_service":   ["customer", "support", "helpdesk", "complaint"],
            "ecommerce":          ["ecommerce", "e-commerce", "order", "product", "cart", "checkout", "shipping", "inventory"],
            "coding_assistant":   ["code", "debug", "lint", "refactor", "developer", "programming", "software", "engineering", "architecture"],
            "finance":            ["financial", "finance", "invoice", "budget", "portfolio", "investment", "trading", "stock", "revenue", "accounting"],
            "data_analysis":      ["data", "analysis", "analytics", "insights", "reporting", "dashboard", "csv", "dataset"],
            "content_creation":   ["content", "writing", "blog", "article", "creative", "copywriting"],
            "project_management": ["project", "manage", "coordinate", "milestone", "deadline", "sprint"],
            "research":           ["research", "investigate", "literature", "study", "explore"],
            "sales_marketing":    ["sales", "marketing", "promote", "campaign", "lead", "crm"],
            "technical_support":  ["technical", "troubleshoot", "maintain", "infrastructure", "devops"],
            "education":          ["teach", "train", "educate", "learn", "course", "student"],
            "healthcare":         ["health", "medical", "patient", "doctor", "clinical", "treatment"],
        }
        for domain, kws in domains.items():
            if any(k in text for k in kws):
                return domain
        return "general"

    def _kw_complexity(self, text: str) -> int:
        score = 1
        if any(w in text for w in ["multi", "pipeline", "workflow", "sequence"]): score += 1
        if any(w in text for w in ["complex", "advanced", "sophisticated"]): score += 1
        if any(w in text for w in ["adaptive", "learning", "dynamic", "intelligent"]): score += 1
        if "real-time" in text or "immediate" in text: score += 1
        return min(score, 5)

    def _kw_interaction(self, text: str) -> str:
        c = sum(1 for w in ["chat", "conversation", "dialogue", "respond", "answer"] if w in text)
        a = sum(1 for w in ["automate", "batch", "schedule", "background", "monitor"] if w in text)
        return "conversational" if c >= a else "automated"

    def _kw_problem_type(self, text: str) -> str:
        if any(w in text for w in ["critical", "permanent", "irreversible", "financial", "safety"]):
            return "irrecoverable"
        if any(w in text for w in ["experiment", "try", "test", "iterative", "adjust"]):
            return "recoverable"
        return "ignorable"

    def _kw_autonomy(self, text: str) -> str:
        if any(w in text for w in ["autonomous", "independent", "self", "automatic"]):
            return "high"
        if any(w in text for w in ["supervised", "guided", "assisted", "human"]):
            return "low"
        return "medium"

    def _kw_capabilities(self, text: str) -> List[str]:
        caps = []
        kw_map = {
            "memory":        ["remember", "recall", "track", "history", "context"],
            "tools":         ["email", "calendar", "search", "file", "database", "api"],
            "reasoning":     ["analyse", "analyze", "reason", "logic", "decide", "evaluate"],
            "communication": ["communicate", "explain", "report", "present"],
            "safety":        ["secure", "safe", "validate", "permission", "audit"],
        }
        for cap, kws in kw_map.items():
            if any(k in text for k in kws):
                caps.append(cap)
        return caps or ["communication"]

    def _kw_agent_type(
        self,
        complexity: int,
        interaction: str,
        problem_type: str,
        autonomy: str,
        caps: List[str],
    ) -> str:
        if problem_type == "irrecoverable" and complexity >= 4:
            return "utility_based"
        if complexity >= 3 and "reasoning" in caps:
            return "goal_based"
        if interaction == "conversational":
            return "conversational"
        if autonomy == "high":
            return "automated"
        if complexity <= 2 and "memory" not in caps:
            return "simple_reflex"
        return "model_based"

    # ── Legacy synchronous wrappers (kept for CLI demo / api.py compat) ───────

    def analyze_job_description(self, job_description: str) -> Dict[str, Any]:
        """Sync alias — runs keyword fallback. Use analyse_with_llm for NLP."""
        return self.analyse_fallback(job_description)

    def recommend_agent_type(self, analysis: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        agent_type = analysis.get("agent_type", "conversational")
        return agent_type, {
            "agent_type": agent_type,
            "rationale": analysis.get("rationale", ""),
            "configuration": AGENT_TYPES.get(agent_type, {}),
            "required_tools": analysis.get("recommended_tools", []),
            "safety_considerations": PROBLEM_TYPES.get(
                analysis.get("problem_type", "ignorable"), {}
            ).get("agent_implications", []),
            "performance_profile": {},
        }

    def generate_system_prompt(self, analysis: Dict[str, Any], recommendation: Dict[str, Any]) -> str:
        return analysis.get("system_prompt") or self._build_system_prompt(analysis)


# ─────────────────────────────────────────────────────────────────────────────
# CLI demo
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio

    SAMPLE_JD = """
    We need an AI agent to help with customer service for our e-commerce platform.
    The agent should be able to answer customer questions about products and orders,
    handle complaints, access our order database, send email notifications, escalate
    complex issues to human agents, remember conversation history, and provide
    real-time responses during business hours. Must be reliable and secure.
    """

    async def demo():
        builder = MetaAgentBuilder()
        print("=== META-AGENT BUILDER ===\n")
        try:
            spec = await builder.analyse_with_llm(SAMPLE_JD)
            src = "LLM"
        except Exception as exc:
            print(f"[Ollama unavailable — using keyword fallback] {exc}\n")
            spec = builder.analyse_fallback(SAMPLE_JD)
            src = "fallback"

        print(f"[source: {src}]")
        for k, v in spec.items():
            if k != "system_prompt":
                print(f"  {k}: {v}")
        print("\n--- System Prompt ---")
        print(spec["system_prompt"])

    asyncio.run(demo())
