from pc_control import execute_pc_command
from screen_vision import handle_screen_command


TOOL_REGISTRY = {
    "screen_reader": {
        "description": "Read or act on the current screen using OCR.",
        "handler": handle_screen_command,
    },
    "pc_control": {
        "description": "Control apps, browser, files, media, and system actions.",
        "handler": execute_pc_command,
    },
}


def list_tools():
    return {name: data["description"] for name, data in TOOL_REGISTRY.items()}


def run_tool(name, payload):
    tool = TOOL_REGISTRY.get(name)
    if not tool:
        return None
    return tool["handler"](payload)
