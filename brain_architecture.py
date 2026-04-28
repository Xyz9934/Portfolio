from dataclasses import dataclass, field
from datetime import datetime

from agents import get_agent_handler
from assistant_memory import add_session_turn, extract_important_memory, get_profile_snapshot, get_session_context, get_task_snapshot, load_profile
from cognitive_background import run_background_cognition_tick
from config import OLLAMA_DEEP_MODEL, OLLAMA_ENABLED, OLLAMA_MODEL, OLLAMA_QUICK_MODEL, PREFER_OFFLINE_BRAIN
from control_profile import normalize_control_mode, profile_to_label
from evolution_engine import ensure_evolution_storage
from identity_model import ensure_identity_storage
from intelligence_metrics import ensure_metrics_storage
from internet_brain import can_handle_live_query
from initiative_engine import ensure_initiative_storage
from knowledge_expansion import ensure_knowledge_task_storage
from life_brain import ensure_life_brain_storage, get_life_brain_context, log_decision, update_profile_from_memory
from personality_engine import apply_personality
from reflection_engine import log_reflection
from task_state import advance_step, fail_task, finish_task, format_task_for_user, start_task
from thought_memory import ensure_thought_memory_storage


@dataclass
class BrainState:
    raw_input: str
    answer_mode: str = "auto"
    normalized_input: str = ""
    created_at: str = ""
    detected_language: str = "english"
    intent: str = "reasoning"
    agent_name: str = "reasoning"
    plan_steps: list = field(default_factory=list)
    memory_context: list = field(default_factory=list)
    live_query_candidate: bool = False
    conversation_window_size: int = 0
    mood_signal: str = "neutral"
    execution_reply: str = ""
    final_reply: str = ""
    response_style: str = "assistant"
    task: dict | None = None
    trace: list = field(default_factory=list)


class FridayBrainArchitecture:
    def __init__(self, planner_callback=None, answer_mode="auto"):
        self.planner_callback = planner_callback
        self.answer_mode = normalize_control_mode(answer_mode)

    def process(self, user_input):
        ensure_life_brain_storage()
        ensure_thought_memory_storage()
        ensure_evolution_storage()
        ensure_metrics_storage()
        ensure_identity_storage()
        ensure_initiative_storage()
        ensure_knowledge_task_storage()
        state = BrainState(raw_input=(user_input or "").strip(), answer_mode=self.answer_mode)
        layers = [
            self.layer_1_perception,
            self.layer_2_guardrails,
            self.layer_3_intent,
            self.layer_4_memory,
            self.layer_5_live_context,
            self.layer_6_planning,
            self.layer_7_routing,
            self.layer_8_execution,
            self.layer_9_reflection,
            self.layer_10_expression,
        ]

        try:
            for layer in layers:
                layer(state)
            return state.final_reply or state.execution_reply or "I couldn't complete that request."
        except Exception as exc:
            failed_task = fail_task(str(exc))
            self.emit_plan_update(failed_task)
            return f"System error occurred: {exc}"

    def layer_1_perception(self, state):
        state.normalized_input = " ".join(state.raw_input.lower().split())
        state.created_at = datetime.now().isoformat(timespec="seconds")
        state.detected_language = detect_language(state.raw_input)
        state.trace.append(f"Layer 1 Input Intelligence: language={state.detected_language}, mode={profile_to_label(state.answer_mode)}.")

    def layer_2_guardrails(self, state):
        state.live_query_candidate = can_handle_live_query(state.raw_input)
        state.conversation_window_size = len(get_session_context(limit=12))
        state.trace.append("Layer 2 Context Awareness: conversation window refreshed.")

    def layer_3_intent(self, state):
        state.intent = detect_intent(state.normalized_input)
        state.trace.append(f"Layer 3 Memory System Gateway: intent={state.intent}.")

    def layer_4_memory(self, state):
        if state.intent in {"memory", "reasoning"}:
            memory_items = (
                get_life_brain_context(limit=6)
                + get_session_context(limit=6)
                + get_profile_snapshot()
                + get_task_snapshot(limit=5)
            )
            deduped = []
            for item in memory_items:
                if item and item not in deduped:
                    deduped.append(item)
            state.memory_context = deduped[:12]
        state.trace.append(f"Layer 4 Knowledge Brain Prep: memory_items={len(state.memory_context)}.")

    def layer_5_live_context(self, state):
        if state.live_query_candidate and state.intent == "reasoning":
            state.intent = "reasoning"
        state.mood_signal = detect_mood_signal(state.raw_input)
        state.trace.append("Layer 5 Reasoning Engine: live context and mood evaluated.")

    def layer_6_planning(self, state):
        state.plan_steps = build_plan(state.raw_input, state.intent)
        state.task = start_task(state.raw_input, state.intent, state.plan_steps)
        self.emit_plan_update(state.task)
        progressed = advance_step("Perception, guardrails, and intent layers completed.")
        if progressed:
            state.task = progressed
            self.emit_plan_update(state.task)
        state.trace.append("Layer 6 Personality Engine Prep: plan created.")

    def layer_7_routing(self, state):
        state.agent_name = select_agent(state.intent)
        progressed = advance_step(f"Selected {state.agent_name} agent.")
        if progressed:
            state.task = progressed
            self.emit_plan_update(state.task)
        state.trace.append("Layer 7 Learning Engine Prep: routing chosen.")

    def layer_8_execution(self, state):
        handler = get_agent_handler(state.agent_name)
        if state.agent_name == "reasoning":
            result = handler(state.raw_input, task=state.task, answer_mode=state.answer_mode)
        else:
            result = handler(state.raw_input, task=state.task)
        if isinstance(result, dict):
            state.execution_reply = (result.get("message") or "").strip()
            state.response_style = (result.get("response_style") or "assistant").strip() or "assistant"
        else:
            state.execution_reply = result
            state.response_style = "assistant"
        progressed = advance_step("Execution layer completed.")
        if progressed:
            state.task = progressed
            self.emit_plan_update(state.task)
        state.trace.append("Layer 8 Automation and Action: execution complete.")

    def layer_9_reflection(self, state):
        reply = refine_response(state.execution_reply, state.intent)
        extract_important_memory(state.raw_input, reply)
        add_session_turn(state.raw_input, reply, intent=state.intent)
        log_reflection(state.raw_input, reply)
        update_profile_from_memory(load_profile())
        run_background_cognition_tick()
        state.execution_reply = reply
        state.trace.append("Layer 9 Multimodal and Reflection: learning signals stored.")

    def layer_10_expression(self, state):
        if state.response_style == "system":
            state.final_reply = state.execution_reply
        else:
            state.final_reply = apply_personality(state.execution_reply, state.raw_input)
        completed = finish_task(state.final_reply)
        if completed:
            state.task = completed
            self.emit_plan_update(state.task)
        log_decision(state.raw_input, state.final_reply, intent=state.intent, decision_type=state.response_style)
        state.trace.append("Layer 10 Master Brain: final response delivered.")

    def emit_plan_update(self, task):
        if self.planner_callback:
            try:
                self.planner_callback(format_task_for_user(task))
            except Exception:
                pass


def detect_intent(normalized_text):
    text = (normalized_text or "").strip()
    tokens = text.split()
    first_two = " ".join(tokens[:2])

    if any(
        phrase in text
        for phrase in (
            "code:",
            "write code",
            "generate code",
            "fix this code",
            "python error",
            "debug",
            "build me a python",
            "build a python",
            "python app",
            "python script",
            "javascript app",
            "write a python",
        )
    ):
        return "code"
    if any(phrase in text for phrase in ("remember", "my name", "my tasks", "task list", "todo", "remind me", "what do you know about me")):
        return "memory"
    explicit_automation_phrases = (
        "create routine",
        "save routine",
        "remember routine",
        "run routine",
        "start routine",
        "launch routine",
        "show routines",
        "list routines",
        "delete routine",
        "remove routine",
        "show routine",
        "schedule routine",
        "unschedule routine",
        "show routine schedules",
        "list routine schedules",
        "learn:",
        "storage status",
        "show storage",
        "check storage",
        "start screen share",
        "stop screen share",
        "shutdown",
        "restart",
        "lock pc",
    )
    if any(phrase in text for phrase in explicit_automation_phrases):
        return "automation"
    command_verbs = {"open", "play", "click", "press", "tap", "search"}
    conversational_prefixes = {
        "i want",
        "i wanna",
        "can you",
        "could you",
        "do you",
        "should i",
        "i will",
        "i like",
        "i need",
        "i am",
        "i'm",
        "no i",
    }
    if tokens:
        starts_like_command = tokens[0] in command_verbs and len(tokens) <= 6
        has_conversational_prefix = first_two in conversational_prefixes or text.startswith("no i ")
        if starts_like_command and not has_conversational_prefix:
            return "automation"
    return "reasoning"


def build_plan(user_input, intent):
    brain_line = get_brain_mode_summary()
    if intent == "automation":
        return [
            "Layer 1: Input intelligence parses the request",
            "Layer 2-3: Context and memory identify the target action",
            f"Layer 4-5: Knowledge and reasoning choose the safest execution path ({brain_line})",
            "Layer 6-8: Personality, learning, and action execution complete the task",
            "Layer 9-10: Reflection and master orchestration finalize the response",
        ]
    if intent == "code":
        return [
            "Layer 1: Input intelligence parses the request",
            "Layer 2-3: Context and memory classify the coding task",
            f"Layer 4-5: Knowledge and reasoning prepare the coding brain ({brain_line})",
            "Layer 6-8: Personality, learning, and execution generate the result",
            "Layer 9-10: Reflection and master orchestration finalize the response",
        ]
    if intent == "memory":
        return [
            "Layer 1: Input intelligence parses the request",
            "Layer 2-3: Context and memory classify the recall/update goal",
            f"Layer 4-5: Knowledge and reasoning validate memory relevance ({brain_line})",
            "Layer 6-8: Personality, learning, and memory execution complete the task",
            "Layer 9-10: Reflection and master orchestration finalize the response",
        ]
    return [
        "Layer 1: Input intelligence parses the request",
        "Layer 2-3: Context and memory build understanding",
        f"Layer 4-5: Knowledge and reasoning think through the answer ({brain_line})",
        "Layer 6-8: Personality, learning, and execution shape the result",
        "Layer 9-10: Reflection and master orchestration finalize the response",
    ]


def select_agent(intent):
    if intent == "automation":
        return "automation"
    if intent == "code":
        return "code"
    if intent == "memory":
        return "memory"
    return "reasoning"


def refine_response(raw_reply, intent):
    reply = (raw_reply or "").strip()
    if not reply:
        return "I couldn't complete that request."

    if intent == "automation" and not reply.endswith("."):
        reply += "."
    return reply


def run_10_layer_brain(user_input, planner_callback=None, answer_mode="auto"):
    architecture = FridayBrainArchitecture(planner_callback=planner_callback, answer_mode=answer_mode)
    return architecture.process(user_input)


def detect_language(text):
    lowered = (text or "").lower()
    hindi_markers = {"kya", "kaise", "nahi", "haan", "bhai", "acha", "accha", "tum", "mera", "meri", "kal"}
    if any(token in lowered.split() for token in hindi_markers):
        return "hinglish"
    return "english"


def detect_mood_signal(text):
    lowered = (text or "").lower()
    if any(word in lowered for word in ("sad", "down", "hurt", "lonely", "upset")):
        return "low"
    if any(word in lowered for word in ("angry", "frustrated", "annoyed", "stuck")):
        return "frustrated"
    if any(word in lowered for word in ("happy", "excited", "great", "amazing")):
        return "positive"
    return "neutral"


def get_brain_mode_summary():
    if OLLAMA_ENABLED:
        if PREFER_OFFLINE_BRAIN:
            return f"offline-first via Ollama quick={OLLAMA_QUICK_MODEL} deep={OLLAMA_DEEP_MODEL}"
        return f"offline fallback via Ollama quick={OLLAMA_QUICK_MODEL} deep={OLLAMA_DEEP_MODEL}"
    return "cloud-first brain routing"
