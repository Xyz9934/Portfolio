# FRIDAY 10-Layer Brain Architecture

FRIDAY now uses a layered brain pipeline in [brain_architecture.py](/D:/FRIDAY/brain_architecture.py) and supports a cloud-plus-offline knowledge core with Ollama.

## Layered Intelligence Stack

1. `Layer 1: Input Intelligence`
Handles normalized input, text cleanup, and basic language detection.

2. `Layer 2: Context Awareness Engine`
Tracks recent conversation state so FRIDAY can resolve references like "open it".

3. `Layer 3: Memory System`
Combines short-term conversation context with long-term preferences, habits, and task memory.

4. `Layer 4: Knowledge Brain`
Uses FRIDAY's knowledge sources and model routing.
Cloud path: Gemini and GPT.
Offline path: Ollama with a local Llama-family model.

5. `Layer 5: Reasoning Engine`
Builds the response plan and decides how to solve the request before answering.

6. `Layer 6: Personality Engine`
Applies FRIDAY's tone and relationship style.

7. `Layer 7: Learning Engine`
Logs interaction outcomes and stores useful corrections or important memories.

8. `Layer 8: Automation + Action Layer`
Executes PC control, screen tools, and other actionable tasks.

9. `Layer 9: Multimodal Intelligence`
Supports screen understanding, OCR-connected workflows, and mood-aware response shaping.

10. `Layer 10: Master Brain`
Acts as the orchestrator that routes, coordinates, and finalizes responses.

## Brain Routing

`thinking_engine.run_friday_request()` delegates to the 10-layer orchestrator.

Current agent routing:

- `reasoning` -> [agents/reasoning_agent.py](/D:/FRIDAY/agents/reasoning_agent.py)
- `memory` -> [agents/memory_agent.py](/D:/FRIDAY/agents/memory_agent.py)
- `automation` -> [agents/automation_agent.py](/D:/FRIDAY/agents/automation_agent.py)
- `code` -> [agents/coder_agent.py](/D:/FRIDAY/agents/coder_agent.py)

## Ollama Offline Brain

FRIDAY now supports an offline local brain through Ollama in [llm_router.py](/D:/FRIDAY/llm_router.py).

Environment variables:

- `OLLAMA_ENABLED=true`
- `OLLAMA_BASE_URL=http://127.0.0.1:11434`
- `OLLAMA_MODEL=llama3.2`
- `OLLAMA_KEEP_ALIVE=10m`
- `PREFER_OFFLINE_BRAIN=true` to use Ollama before cloud providers

Behavior:

- If `PREFER_OFFLINE_BRAIN=true`, FRIDAY tries Ollama first, then Gemini/GPT.
- If `PREFER_OFFLINE_BRAIN=false`, FRIDAY uses Ollama as an offline fallback.
- `local_ai_core.py` now uses the model router instead of acting like a plain web-search stub.
