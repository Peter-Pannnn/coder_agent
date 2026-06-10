"""Main agent orchestration for repository questions."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from langchain_core.runnables import Runnable

from .answer_chain import get_answer_chain
from .tool_routing_agent import ToolRoutingAgent, ToolRoutingDecision, get_tool_routing_agent


@dataclass(frozen=True)
class CoderAgentResult:
    """Final result returned by the main coder agent."""

    input: str
    answer: str
    routing_decision: ToolRoutingDecision


class ToolExecutionNotImplementedError(NotImplementedError):
    """Raised when routing decides tools are needed but tool execution is not ready."""

    def __init__(self, routing_decision: ToolRoutingDecision):
        self.routing_decision = routing_decision
        tool_names = ", ".join(tool.name for tool in routing_decision.tools)
        message = f"Tool execution is not implemented yet. Requested tools: {tool_names}"
        super().__init__(message)


class CoderAgent:
    """Main Agent that routes first, then answers or delegates to tools."""

    def __init__(
        self,
        routing_agent: ToolRoutingAgent,
        answer_chain: Runnable,
    ):
        self.routing_agent = routing_agent
        self.answer_chain = answer_chain

    def run(self, user_input: str) -> CoderAgentResult:
        """Route the request and handle the no-tool answer path."""
        self._validate_user_input(user_input)

        routing_decision = self.routing_agent.route(user_input)

        if routing_decision.needs_tools:
            raise ToolExecutionNotImplementedError(routing_decision)

        answer = self.answer_chain.invoke({"input": user_input})
        return CoderAgentResult(
            input=user_input,
            answer=answer,
            routing_decision=routing_decision,
        )

    def stream(self, user_input: str) -> Iterator[str]:
        """Route the request and stream the no-tool answer text."""
        self._validate_user_input(user_input)

        routing_decision = self.routing_agent.route(user_input)

        if routing_decision.needs_tools:
            raise ToolExecutionNotImplementedError(routing_decision)

        yield from self.answer_chain.stream({"input": user_input})

    def _validate_user_input(self, user_input: str) -> None:
        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError("user_input must be a non-empty string.")


def get_coder_agent(
    model: Any | None = None,
    temperature: float = 0.2,
    answer_chain: Runnable | None = None,
) -> CoderAgent:
    """Create the main coder agent with one shared model client."""
    if model is None:
        from src.models import get_ali_model_client

        model = get_ali_model_client(temperature=temperature)

    routing_agent = get_tool_routing_agent(model=model)
    if answer_chain is None:
        answer_chain = get_answer_chain(model=model)

    return CoderAgent(routing_agent=routing_agent, answer_chain=answer_chain)
