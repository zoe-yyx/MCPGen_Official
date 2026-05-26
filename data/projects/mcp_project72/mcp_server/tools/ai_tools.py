"""AI Hotel Agent for mcp_project72 — GPT with tool calling for hotel queries."""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from .hotel_data_tools import execute_sql_query, get_pricing, get_db_schema
from .utils.log_decorator import log_mcp_call

load_dotenv()

_SYSTEM_PROMPT_TEMPLATE = """\
You are a helpful AI receptionist for Grand Palace Hotel.
You assist guests with questions about room availability, bookings, check-in/check-out times, and pricing.

You have access to two tools:
1. execute_sql_query — runs a read-only SELECT query on the hotel database
2. get_room_pricing — retrieves room pricing from our pricing sheet

{schema}

SECURITY RULES (strictly enforced):
- You may ONLY use SELECT statements. Never INSERT, UPDATE, DELETE, DROP, or ALTER.
- If a guest asks to make a booking or change data, politely explain that they should contact the front desk.

Always respond in a friendly, professional tone. Keep answers concise and clear.\
"""

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_sql_query",
            "description": "Execute a read-only SQL SELECT query on the hotel database to answer guest questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A valid SQL SELECT statement.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_room_pricing",
            "description": "Get the hotel room pricing sheet with weekday/weekend rates, extra bed fees, and breakfast info.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

# Per-user conversation memory: {wa_id: [{"role": ..., "content": ...}]}
_MEMORY: dict[str, list[dict]] = {}
_MAX_HISTORY = 10  # keep last N turns


def _load_memory(wa_id: str) -> list[dict]:
    if wa_id not in _MEMORY:
        path = f"results/outputs/memory_{wa_id}.json"
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    _MEMORY[wa_id] = json.load(f)
            except Exception:
                _MEMORY[wa_id] = []
        else:
            _MEMORY[wa_id] = []
    return _MEMORY[wa_id]


def _save_memory(wa_id: str) -> None:
    os.makedirs("results/outputs", exist_ok=True)
    path = f"results/outputs/memory_{wa_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_MEMORY.get(wa_id, []), f, indent=2, ensure_ascii=False)


@log_mcp_call("tool", "ai_hotel_agent")
def ai_hotel_agent(user_message: str, wa_id: str = "guest", model_index: int = 0) -> str:
    """GPT-powered hotel agent with SQL and pricing tools. Maintains per-user memory."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "ENDPOINT_PLACEHOLDER")
    model = os.getenv("MODEL", "gpt-5.1")

    client = OpenAI(api_key=api_key, base_url=base_url)
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(schema=get_db_schema())

    history = _load_memory(wa_id)
    history.append({"role": "user", "content": user_message})
    # Trim to last N turns
    if len(history) > _MAX_HISTORY * 2:
        history = history[-(  _MAX_HISTORY * 2):]

    messages = [{"role": "system", "content": system_prompt}] + history

    # Agent loop: call GPT, handle tool calls, repeat until final answer
    max_iterations = 5
    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=_TOOLS,
            tool_choice="auto",
            temperature=0.3,
        )
        msg = response.choices[0].message

        if msg.tool_calls:
            messages.append(msg)
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments or "{}")

                if fn_name == "execute_sql_query":
                    tool_result = execute_sql_query(fn_args.get("query", "SELECT 1"))
                elif fn_name == "get_room_pricing":
                    tool_result = get_pricing()
                else:
                    tool_result = json.dumps({"error": f"Unknown tool: {fn_name}"})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result,
                })
        else:
            # Final answer
            answer = (msg.content or "").strip()
            history.append({"role": "assistant", "content": answer})
            _MEMORY[wa_id] = history
            _save_memory(wa_id)
            return json.dumps({
                "output": answer,
                "wa_id": wa_id,
                "model_index": model_index,
            })

    # Fallback if max iterations reached
    fallback = "I'm sorry, I couldn't retrieve the information right now. Please contact the front desk."
    history.append({"role": "assistant", "content": fallback})
    _MEMORY[wa_id] = history
    return json.dumps({"output": fallback, "wa_id": wa_id, "model_index": model_index})
