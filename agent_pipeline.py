from dataclasses import dataclass, field

from llm_router import ask_friday_llm_ultra
from ultra_intelligence import estimate_confidence, format_confidence_line


@dataclass
class AgentStageResult:
    stage: str
    output: str = ""
    status: str = "pending"
    attempts: int = 0
    notes: list = field(default_factory=list)


@dataclass
class AgentPipelineState:
    user_input: str
    private_context: list = field(default_factory=list)
    life_context: list = field(default_factory=list)
    memory_context: list = field(default_factory=list)
    planner: AgentStageResult = field(default_factory=lambda: AgentStageResult(stage="planner"))
    researcher: AgentStageResult = field(default_factory=lambda: AgentStageResult(stage="researcher"))
    critic: AgentStageResult = field(default_factory=lambda: AgentStageResult(stage="critic"))
    executor: AgentStageResult = field(default_factory=lambda: AgentStageResult(stage="executor"))
    shared_notes: list = field(default_factory=list)


class BaseAgentModule:
    stage_name = "base"
    max_attempts = 2

    def run(self, state):
        stage = self._get_stage(state)
        for attempt in range(1, self.max_attempts + 1):
            stage.attempts = attempt
            try:
                output = (self.produce(state) or "").strip()
            except Exception as exc:
                output = f"Stage error: {exc}"
            if self.is_acceptable(output):
                stage.output = output
                stage.status = "completed"
                return stage
            stage.notes.append(f"Attempt {attempt} produced weak output.")
        stage.output = output
        stage.status = "failed"
        return stage

    def produce(self, state):
        return ""

    def is_acceptable(self, output):
        return bool((output or "").strip())

    def _get_stage(self, state):
        return getattr(state, self.stage_name)


class PlannerAgentModule(BaseAgentModule):
    stage_name = "planner"

    def produce(self, state):
        prompt = f"""
You are FRIDAY's Planner Agent.
Break the user's request into a short execution plan.
Return concise plain text with:
1. Objective
2. Steps
3. Success check

User request:
{state.user_input}
""".strip()
        answer, _, _ = ask_friday_llm_ultra(prompt, extra_system_prompt="Be structured, practical, and concise.")
        return answer


class ResearchAgentModule(BaseAgentModule):
    stage_name = "researcher"

    def produce(self, state):
        lines = ["Research context summary:"]
        if state.private_context:
            lines.append("Private knowledge:")
            lines.extend(f"- {item}" for item in state.private_context[:4])
        if state.life_context:
            lines.append("Life brain context:")
            lines.extend(f"- {item}" for item in state.life_context[:4])
        if state.memory_context:
            lines.append("Memory context:")
            lines.extend(f"- {item}" for item in state.memory_context[:4])
        if len(lines) == 1:
            lines.append("- No extra context available.")
        return "\n".join(lines)


class CriticAgentModule(BaseAgentModule):
    stage_name = "critic"

    def produce(self, state):
        prompt = f"""
You are FRIDAY's Critic Agent.
Review the planner and researcher outputs.
List the biggest risks, gaps, or assumptions in 3 bullet points max.

Planner output:
{state.planner.output}

Research output:
{state.researcher.output}

User request:
{state.user_input}
""".strip()
        answer, _, _ = ask_friday_llm_ultra(prompt, extra_system_prompt="Be skeptical, but constructive and concise.")
        return answer


class ExecutionAgentModule(BaseAgentModule):
    stage_name = "executor"

    def produce(self, state):
        prompt = f"""
You are FRIDAY's Execution Agent.
Use the planner, researcher, and critic handoff to answer the user.
Return a direct final answer, not your chain-of-thought.

User request:
{state.user_input}

Planner handoff:
{state.planner.output}

Research handoff:
{state.researcher.output}

Critic handoff:
{state.critic.output}
""".strip()
        answer, _, _ = ask_friday_llm_ultra(prompt, extra_system_prompt="Give the best final answer with actionable next steps when appropriate.")
        return answer


def run_agent_pipeline(user_input, private_context=None, life_context=None, memory_context=None):
    state = AgentPipelineState(
        user_input=(user_input or "").strip(),
        private_context=private_context or [],
        life_context=life_context or [],
        memory_context=memory_context or [],
    )
    stages = [
        PlannerAgentModule(),
        ResearchAgentModule(),
        CriticAgentModule(),
        ExecutionAgentModule(),
    ]
    for module in stages:
        module.run(state)

    final_answer = state.executor.output or state.planner.output or "I couldn't complete the autonomous pipeline."
    confidence = estimate_confidence(
        user_input,
        final_answer,
        (private_context or []) + (life_context or []) + (memory_context or []),
    )
    return format_pipeline_output(state, final_answer, confidence), state


def format_pipeline_output(state, final_answer, confidence):
    lines = [
        "Autonomous pipeline result:",
        "Planner stage:",
        state.planner.output or "No planner output.",
        "",
        "Research stage:",
        state.researcher.output or "No research output.",
        "",
        "Critic stage:",
        state.critic.output or "No critic output.",
        "",
        "Execution stage:",
        final_answer,
        "",
        format_confidence_line(confidence),
    ]
    return "\n".join(lines)
