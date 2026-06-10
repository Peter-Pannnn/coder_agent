"""Public prompt interfaces for the coder agent."""

from .system_prompt import SYSTEM_PROMPT, get_chat_prompt, get_system_message_prompt
from .tool_routing_prompt import (
    TOOL_ROUTING_PROMPT,
    get_tool_routing_chat_prompt,
    get_tool_routing_message_prompt,
)

__all__ = [
    "SYSTEM_PROMPT",
    "TOOL_ROUTING_PROMPT",
    "get_chat_prompt",
    "get_system_message_prompt",
    "get_tool_routing_chat_prompt",
    "get_tool_routing_message_prompt",
]
