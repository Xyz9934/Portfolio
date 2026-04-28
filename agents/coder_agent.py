import os

from coder_brain import run_code_mode


def handle_coding_task(user_input, task=None):
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.dirname(workspace_dir)
    return run_code_mode(user_input, workspace_dir)
