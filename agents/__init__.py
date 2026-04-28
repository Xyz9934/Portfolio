from .automation_agent import handle_automation_task
from .coder_agent import handle_coding_task
from .memory_agent import handle_memory_task
from .reasoning_agent import handle_reasoning_task


AGENT_REGISTRY = {
    "automation": handle_automation_task,
    "code": handle_coding_task,
    "memory": handle_memory_task,
    "reasoning": handle_reasoning_task,
}


def get_agent_handler(agent_name):
    return AGENT_REGISTRY.get(agent_name, handle_reasoning_task)
