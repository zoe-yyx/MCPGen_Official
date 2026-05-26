"""Chat tools - AI Agent with memory and knowledge base.

Corresponds to n8n nodes:
- AI Agent: orchestrate chat with LLM using knowledge base context
- OpenAI Chat Model: call OpenAI-compatible LLM
- Simple Memory: maintain conversation history buffer
- Knowledge Base GraphRAG: integrated via graph_tools.query_knowledge_base
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

from .utils.log_decorator import log_mcp_call
from .graph_tools import query_knowledge_base

load_dotenv()


class ConversationMemory:
    """Simple buffer window memory for conversation history."""

    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self.history: list[dict[str, str]] = []

    def add_message(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.max_turns * 2:
            self.history = self.history[-(self.max_turns * 2):]

    def get_messages(self) -> list[dict[str, str]]:
        return list(self.history)

    def clear(self) -> None:
        self.history.clear()


# Module-level shared memory instance
_memory = ConversationMemory()


@log_mcp_call("tool", "chat_with_knowledge_base")
def chat_with_knowledge_base(
    user_message: str,
    graph_name: str,
    store_path: str,
) -> str:
    """Chat with documents using GraphRAG knowledge base and LLM.

    This tool queries the knowledge base for relevant context,
    then sends the user message + context to the LLM for a response.

    Args:
        user_message: The user's question or message.
        graph_name: Name of the graph to query for context.
        store_path: Path to the graph store JSON file.

    Returns:
        The AI assistant's response string.
    """
    # Step 1: Query knowledge base for relevant context
    kb_result = query_knowledge_base(
        graph_name=graph_name,
        prompt=user_message,
        store_path=store_path,
    )

    context_text = ""
    if kb_result["relevant_statements"]:
        context_text = "\n\n".join(kb_result["relevant_statements"])
    summary = kb_result.get("summary", "")

    # Step 2: Build messages with system prompt, memory, and context
    system_prompt = (
        "You provide information about the topic of user's interest. "
        "Always use the knowledge base context attached to get the final response.\n\n"
        f"Knowledge Base Summary: {summary}\n\n"
        f"Relevant Context:\n{context_text}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(_memory.get_messages())
    messages.append({"role": "user", "content": user_message})

    # Step 3: Call OpenAI-compatible LLM
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )
    model = os.getenv("OPENAI_MODEL", "gpt-5.1")

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7,
        max_tokens=1024,
    )

    assistant_reply = response.choices[0].message.content

    # Step 4: Update memory
    _memory.add_message("user", user_message)
    _memory.add_message("assistant", assistant_reply)

    return assistant_reply


@log_mcp_call("tool", "clear_memory")
def clear_memory() -> str:
    """Clear the conversation memory buffer.

    Returns:
        Confirmation message.
    """
    _memory.clear()
    return "Conversation memory cleared."
