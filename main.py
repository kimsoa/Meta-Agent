# This system analyzes job descriptions and creates appropriate AI agents

import json
import re
from typing import Dict, List, Tuple, Any
from datetime import datetime
import uuid

class MetaAgentBuilder:
    """
    Meta-agent that creates specialized AI agents based on job descriptions
    Implements agent type classification and system prompt generation
    """
    
    def __init__(self):
        # AI Agent Types from research [1]
        self.agent_types = {
            "simple_reflex": {
                "description": "Fast reactive agent with no memory, responds to current input only",
                "use_cases": ["real-time monitoring", "threshold-based alerts", "simple automation"],
                "characteristics": ["fast execution", "no memory", "rule-based decisions"],
                "complexity": 1
            },
            "model_based": {
                "description": "Agent with internal world model and memory of past states",
                "use_cases": ["data analysis", "tracking systems", "state management"],
                "characteristics": ["internal model", "memory", "state tracking"],
                "complexity": 2
            },
            "goal_based": {
                "description": "Agent that works towards explicit goals with planning",
                "use_cases": ["project management", "task completion", "strategic planning"],
                "characteristics": ["goal-oriented", "planning", "adaptation"],
                "complexity": 3
            },
            "utility_based": {
                "description": "Agent that optimizes for utility/happiness metrics",
                "use_cases": ["optimization tasks", "resource allocation", "decision making"],
                "characteristics": ["utility evaluation", "preference ranking", "optimization"],
                "complexity": 4
            },
            "conversational": {
                "description": "Agent focused on natural language interaction",
                "use_cases": ["customer service", "assistance", "information retrieval"],
                "characteristics": ["dialogue management", "context retention", "user interaction"],
                "complexity": 3
            },
            "automated": {
                "description": "Agent that runs background tasks without human intervention",
                "use_cases": ["data processing", "system monitoring", "batch operations"],
                "characteristics": ["autonomous operation", "scheduled tasks", "minimal interaction"],
                "complexity": 2
            }
        }
        
        # Problem Types from research [2]
        self.problem_types = {
            "ignorable": {
                "description": "Problems where some steps can be skipped without impact",
                "agent_implications": ["simpler heuristics", "lower computational budget"],
                "examples": ["optimization with negligible variables", "approximate solutions"]
            },
            "recoverable": {
                "description": "Problems where mistakes can be undone or corrected",
                "agent_implications": ["rollback mechanisms", "exploratory planning"],
                "examples": ["game playing", "iterative design", "trial and error tasks"]
            },
            "irrecoverable": {
                "description": "Problems where actions are permanent and mistakes costly",
                "agent_implications": ["strong safety checks", "utility-based evaluation"],
                "examples": ["financial transactions", "safety-critical systems", "permanent decisions"]
            }
        }
        
        # Core capabilities mapping
        self.capabilities = {
            "memory": ["conversation_history", "knowledge_base", "user_preferences", "session_state"],
            "tools": ["email", "calendar", "web_search", "file_operations", "api_calls", "database_queries"],
            "reasoning": ["logical_inference", "causal_reasoning", "probabilistic_reasoning", "temporal_reasoning"],
            "communication": ["natural_language", "structured_output", "multilingual", "tone_adaptation"],
            "safety": ["input_validation", "output_filtering", "permission_checking", "audit_logging"]
        }

    def analyze_job_description(self, job_description: str) -> Dict[str, Any]:
        """Analyze job description to extract key requirements and classify problem type"""
        
        # Clean and normalize text
        text = job_description.lower().strip()
        
        # Extract key indicators
        analysis = {
            "raw_jd": job_description,
            "domain": self._identify_domain(text),
            "complexity_level": self._assess_complexity(text),
            "interaction_type": self._determine_interaction_type(text),
            "required_capabilities": self._extract_capabilities(text),
            "problem_type": self._classify_problem_type(text),
            "autonomy_level": self._assess_autonomy_level(text),
            "performance_requirements": self._extract_performance_requirements(text)
        }
        
        return analysis

    def _identify_domain(self, text: str) -> str:
        """Identify the primary domain/industry"""
        domains = {
            "customer_service": ["customer", "support", "service", "help", "assistance"],
            "data_analysis": ["data", "analysis", "analytics", "insights", "reporting"],
            "content_creation": ["content", "writing", "creative", "generate", "create"],
            "project_management": ["project", "manage", "coordinate", "plan", "organize"],
            "research": ["research", "investigate", "analyze", "study", "explore"],
            "sales_marketing": ["sales", "marketing", "promote", "sell", "campaign"],
            "technical_support": ["technical", "troubleshoot", "debug", "maintain", "system"],
            "education": ["teach", "train", "educate", "learn", "instruct"],
            "finance": ["financial", "money", "budget", "cost", "revenue"],
            "healthcare": ["health", "medical", "patient", "care", "treatment"]
        }
        
        for domain, keywords in domains.items():
            if any(keyword in text for keyword in keywords):
                return domain
        return "general"

    def _assess_complexity(self, text: str) -> int:
        """Assess complexity level (1-5)"""
        complexity_indicators = {
            "simple": ["simple", "basic", "straightforward", "easy"],
            "moderate": ["moderate", "standard", "typical", "regular"],
            "complex": ["complex", "advanced", "sophisticated", "intricate"],
            "multi_step": ["multi", "sequence", "workflow", "process", "pipeline"],
            "adaptive": ["adaptive", "learning", "evolving", "dynamic", "intelligent"]
        }
        
        score = 1
        if any(word in text for word in complexity_indicators["multi_step"]): score += 1
        if any(word in text for word in complexity_indicators["complex"]): score += 1
        if any(word in text for word in complexity_indicators["adaptive"]): score += 1
        if "real-time" in text or "immediate" in text: score += 1
        
        return min(score, 5)

    def _determine_interaction_type(self, text: str) -> str:
        """Determine if agent should be conversational or automated"""
        conversational_indicators = ["chat", "talk", "conversation", "dialogue", "interact", "respond", "answer"]
        automated_indicators = ["automate", "batch", "schedule", "background", "monitor", "track"]
        
        conv_score = sum(1 for indicator in conversational_indicators if indicator in text)
        auto_score = sum(1 for indicator in automated_indicators if indicator in text)
        
        return "conversational" if conv_score > auto_score else "automated"

    def _extract_capabilities(self, text: str) -> List[str]:
        """Extract required capabilities from job description"""
        required_caps = []
        
        capability_keywords = {
            "memory": ["remember", "recall", "track", "history", "context", "previous"],
            "tools": ["email", "calendar", "search", "file", "database", "api", "integrate"],
            "reasoning": ["analyze", "reason", "logic", "decide", "evaluate", "assess"],
            "communication": ["communicate", "explain", "describe", "report", "present"],
            "safety": ["secure", "safe", "validate", "check", "permission", "audit"]
        }
        
        for capability, keywords in capability_keywords.items():
            if any(keyword in text for keyword in keywords):
                required_caps.append(capability)
        
        return required_caps

    def _classify_problem_type(self, text: str) -> str:
        """Classify the problem type based on job description"""
        if any(word in text for word in ["critical", "permanent", "irreversible", "financial", "safety"]):
            return "irrecoverable"
        elif any(word in text for word in ["experiment", "try", "test", "iterative", "adjust"]):
            return "recoverable"
        else:
            return "ignorable"

    def _assess_autonomy_level(self, text: str) -> str:
        """Assess required autonomy level"""
        if any(word in text for word in ["autonomous", "independent", "self", "automatic"]):
            return "high"
        elif any(word in text for word in ["supervised", "guided", "assisted", "human"]):
            return "low"
        else:
            return "medium"

    def _extract_performance_requirements(self, text: str) -> Dict[str, str]:
        """Extract performance and efficiency requirements"""
        requirements = {}
        
        if any(word in text for word in ["fast", "quick", "immediate", "real-time"]):
            requirements["speed"] = "high"
        elif any(word in text for word in ["batch", "scheduled", "background"]):
            requirements["speed"] = "standard"
        
        if any(word in text for word in ["scale", "volume", "many", "thousands"]):
            requirements["scalability"] = "high"
        
        if any(word in text for word in ["accurate", "precise", "correct", "reliable"]):
            requirements["accuracy"] = "high"
        
        return requirements

    def recommend_agent_type(self, analysis: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Recommend the best agent type based on analysis"""
        
        complexity = analysis["complexity_level"]
        interaction = analysis["interaction_type"]
        problem_type = analysis["problem_type"]
        autonomy = analysis["autonomy_level"]
        
        # Decision logic based on research findings
        if problem_type == "irrecoverable" and complexity >= 4:
            agent_type = "utility_based"
        elif complexity >= 3 and "reasoning" in analysis["required_capabilities"]:
            agent_type = "goal_based"
        elif interaction == "conversational":
            agent_type = "conversational"
        elif autonomy == "high" and interaction == "automated":
            agent_type = "automated"
        elif complexity <= 2 and "memory" not in analysis["required_capabilities"]:
            agent_type = "simple_reflex"
        else:
            agent_type = "model_based"
        
        recommendation = {
            "agent_type": agent_type,
            "rationale": self._generate_rationale(analysis, agent_type),
            "configuration": self.agent_types[agent_type],
            "required_tools": self._map_tools(analysis["required_capabilities"]),
            "safety_considerations": self._generate_safety_recommendations(problem_type),
            "performance_profile": analysis["performance_requirements"]
        }
        
        return agent_type, recommendation

    def _generate_rationale(self, analysis: Dict[str, Any], agent_type: str) -> str:
        """Generate human-readable rationale for agent type selection"""
        complexity = analysis["complexity_level"]
        domain = analysis["domain"]
        problem_type = analysis["problem_type"]
        
        rationale = f"Selected {agent_type} agent based on: "
        rationale += f"complexity level {complexity}/5 in {domain} domain, "
        rationale += f"{problem_type} problem type, "
        rationale += f"requiring {', '.join(analysis['required_capabilities'])} capabilities."
        
        return rationale

    def _map_tools(self, capabilities: List[str]) -> List[str]:
        """Map capabilities to specific tools"""
        tool_mapping = []
        for capability in capabilities:
            if capability in self.capabilities:
                tool_mapping.extend(self.capabilities[capability])
        
        return list(set(tool_mapping))  # Remove duplicates

    def _generate_safety_recommendations(self, problem_type: str) -> List[str]:
        """Generate safety recommendations based on problem type"""
        safety_map = {
            "irrecoverable": [
                "Implement strong validation gates",
                "Require explicit confirmation for destructive actions",
                "Add comprehensive audit logging",
                "Implement rollback mechanisms where possible"
            ],
            "recoverable": [
                "Enable undo functionality",
                "Implement checkpoint saving",
                "Add progress tracking",
                "Enable iterative refinement"
            ],
            "ignorable": [
                "Basic input validation",
                "Standard error handling",
                "Simple logging"
            ]
        }
        
        return safety_map.get(problem_type, safety_map["ignorable"])

    def generate_system_prompt(self, analysis: Dict[str, Any], recommendation: Dict[str, Any]) -> str:
        """Generate comprehensive system prompt for the agent"""
        
        agent_type = recommendation["agent_type"]
        domain = analysis["domain"]
        capabilities = analysis["required_capabilities"]
        tools = recommendation["required_tools"]
        
        prompt_template = f"""
# AI Agent System Prompt
## Agent Configuration: {agent_type.title().replace('_', ' ')} Agent

### Primary Role & Identity
You are a specialized {agent_type.replace('_', ' ')} AI agent designed for {domain} tasks.

### Core Characteristics
Based on the {agent_type} architecture, you exhibit the following characteristics:
{self._format_characteristics(recommendation["configuration"]["characteristics"])}

### Problem-Solving Approach
You are designed to handle {analysis["problem_type"]} problems, which means:
{self._format_problem_approach(analysis["problem_type"])}

### Required Capabilities
You have been equipped with the following core capabilities:
{self._format_capabilities(capabilities)}

### Available Tools
You have access to the following tools to accomplish your tasks:
{self._format_tools(tools)}

### Operational Guidelines
{self._generate_operational_guidelines(analysis, recommendation)}

### Safety & Constraints
{self._format_safety_guidelines(recommendation["safety_considerations"])}

### Performance Expectations
{self._format_performance_expectations(analysis.get("performance_requirements", {}))}

### Additional Instructions
- Always maintain context and coherence in your responses
- Prioritize user safety and data security
- Provide clear explanations for your reasoning when appropriate
- Ask for clarification when requirements are ambiguous
- Continuously learn and adapt from interactions within your capabilities

Remember: Your primary goal is to excel in {domain} tasks while maintaining the {agent_type} approach to problem-solving.
"""
        
        return prompt_template.strip()

    def _format_characteristics(self, characteristics: List[str]) -> str:
        return "\n".join([f"- {char.title().replace('_', ' ')}" for char in characteristics])

    def _format_problem_approach(self, problem_type: str) -> str:
        return "\n".join([f"- {impl}" for impl in self.problem_types[problem_type]["agent_implications"]])

    def _format_capabilities(self, capabilities: List[str]) -> str:
        return "\n".join([f"- {cap.title().replace('_', ' ')}: Enabled" for cap in capabilities])

    def _format_tools(self, tools: List[str]) -> str:
        return "\n".join([f"- {tool.replace('_', ' ').title()}" for tool in tools])

    def _generate_operational_guidelines(self, analysis: Dict[str, Any], recommendation: Dict[str, Any]) -> str:
        guidelines = [
            f"- Operate with {analysis['autonomy_level']} autonomy level",
            f"- Focus on {analysis['interaction_type']} interactions",
            f"- Maintain complexity level appropriate for {analysis['complexity_level']}/5 tasks"
        ]
        
        return "\n".join(guidelines)

    def _format_safety_guidelines(self, safety_considerations: List[str]) -> str:
        return "\n".join([f"- {consideration}" for consideration in safety_considerations])

    def _format_performance_expectations(self, performance_reqs: Dict[str, str]) -> str:
        if not performance_reqs:
            return "- Standard performance expectations apply"
        
        expectations = []
        for req_type, level in performance_reqs.items():
            expectations.append(f"- {req_type.title()}: {level} priority")
        
        return "\n".join(expectations)

if __name__ == "__main__":
    # Standalone demo — run directly with: python main.py
    meta_agent = MetaAgentBuilder()

    sample_jd = """
    We need an AI agent to help with customer service for our e-commerce platform.
    The agent should be able to:
    - Answer customer questions about products and orders
    - Handle complaints and provide solutions
    - Access our order database to check order status
    - Send email notifications to customers
    - Escalate complex issues to human agents
    - Remember conversation history for better context
    - Provide real-time responses during business hours
    The agent needs to be reliable and secure since it deals with customer data.
    """

    print("=== META-AGENT BUILDER DEMONSTRATION ===")
    print("\nInput Job Description:")
    print(sample_jd)
    print("\n" + "=" * 60)

    analysis = meta_agent.analyze_job_description(sample_jd)
    print("\n1. JOB DESCRIPTION ANALYSIS:")
    for key, value in analysis.items():
        if key != "raw_jd":
            print(f"   {key.replace('_', ' ').title()}: {value}")

    agent_type, recommendation = meta_agent.recommend_agent_type(analysis)
    print(f"\n2. RECOMMENDED AGENT TYPE: {agent_type.upper()}")
    print(f"   Rationale: {recommendation['rationale']}")

    print(f"\n3. CONFIGURATION DETAILS:")
    print(f"   Agent Characteristics: {recommendation['configuration']['characteristics']}")
    print(f"   Required Tools: {recommendation['required_tools']}")
    print(f"   Safety Considerations: {len(recommendation['safety_considerations'])} items")

    system_prompt = meta_agent.generate_system_prompt(analysis, recommendation)
    print(f"\n4. GENERATED SYSTEM PROMPT:")
    print("=" * 60)
    print(system_prompt)
    print("=" * 60)

    print(f"\n5. AGENT CREATION SUMMARY:")
    print(f"   ✅ Agent Type: {agent_type}")
    print(f"   ✅ Domain: {analysis['domain']}")
    print(f"   ✅ Complexity: {analysis['complexity_level']}/5")
    print(f"   ✅ Capabilities: {len(analysis['required_capabilities'])} core features")
    print(f"   ✅ Tools: {len(recommendation['required_tools'])} integrated tools")
    print(f"   ✅ Safety: {analysis['problem_type']} problem handling")