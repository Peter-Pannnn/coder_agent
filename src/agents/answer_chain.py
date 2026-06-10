"""Answer chain builder for direct no-tool responses."""

from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable
from src.prompt import get_chat_prompt

def get_answer_chain(model: Runnable) -> Runnable:
    """Build the LangChain chain used when no repository tools are needed."""
    prompt = get_chat_prompt()

    return prompt | model | StrOutputParser()
