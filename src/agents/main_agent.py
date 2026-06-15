"""Main agent orchestration for repository questions."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from langchain_core.runnables import Runnable

from .answer_chain import get_answer_chain
from .tool_routing_agent import ToolCallDecision, ToolRoutingAgent, ToolRoutingDecision, get_tool_routing_agent


REQUIRED_TOOL_INPUTS: dict[str, tuple[str, ...]] = {
    "read_file": ("file_path",),
    "search_code": ("query",),
    "index_repository": ("target_path",),
    "retrieve_context": ("query",),
}


@dataclass(frozen=True)
class ToolExecutionResult:
    """Result returned by one repository tool call."""

    name: str
    input: dict[str, Any]
    output: str
    error: str = ""


@dataclass(frozen=True)
class CoderAgentResult:
    """Final result returned by the main coder agent."""

    input: str
    answer: str
    routing_decision: ToolRoutingDecision
    tool_results: list[ToolExecutionResult] = field(default_factory=list)


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
        tools: dict[str, Any] | None = None,
    ):
        self.routing_agent = routing_agent
        self.answer_chain = answer_chain
        self.tools = tools

    def run(self, user_input: str) -> CoderAgentResult:
        """Route the request, run tools when needed, and return the final answer."""
        self._validate_user_input(user_input)

        routing_decision = self.routing_agent.route(user_input)
        if routing_decision.needs_tools:
            answer, tool_results = self._answer_with_tools(user_input, routing_decision)
            return CoderAgentResult(
                input=user_input,
                answer=answer,
                routing_decision=routing_decision,
                tool_results=tool_results,
            )

        answer = self.answer_chain.invoke({"input": user_input})
        return CoderAgentResult(
            input=user_input,
            answer=answer,
            routing_decision=routing_decision,
        )

    def stream(self, user_input: str) -> Iterator[str]:
        """Route the request, run tools when needed, and stream the final answer."""
        self._validate_user_input(user_input)

        routing_decision = self.routing_agent.route(user_input)
        print(routing_decision)

        if routing_decision.needs_tools:
            context, _ = self._prepare_tool_context(routing_decision)
            yield from self.answer_chain.stream({"input": user_input, "context": context})
            return

        yield from self.answer_chain.stream({"input": user_input})

    def _validate_user_input(self, user_input: str) -> None:
        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError("user_input must be a non-empty string.")

    def _answer_with_tools(
        self,
        user_input: str,
        routing_decision: ToolRoutingDecision,
    ) -> tuple[str, list[ToolExecutionResult]]:
        context, tool_results = self._prepare_tool_context(routing_decision)
        answer = self.answer_chain.invoke({"input": user_input, "context": context})
        return answer, tool_results

    def _prepare_tool_context(
        self,
        routing_decision: ToolRoutingDecision,
    ) -> tuple[str, list[ToolExecutionResult]]:
        missing_inputs = self._find_missing_inputs(routing_decision)
        if missing_inputs:
            return self._build_clarifying_context(routing_decision, missing_inputs), []

        tool_results = self._execute_tools(routing_decision)
        return self._build_tool_context(routing_decision, tool_results), tool_results

    def _find_missing_inputs(self, routing_decision: ToolRoutingDecision) -> list[str]:
        missing: list[str] = []
        for tool_call in routing_decision.tools:
            required_keys = REQUIRED_TOOL_INPUTS.get(tool_call.name, ())
            missing_keys = [key for key in required_keys if key not in tool_call.suggested_input]
            if missing_keys:
                missing.append(f"{tool_call.name}: {', '.join(missing_keys)}")
        return missing

    def _execute_tools(self, routing_decision: ToolRoutingDecision) -> list[ToolExecutionResult]:
        tools = self.tools if self.tools is not None else self._load_repository_tools()
        results: list[ToolExecutionResult] = []
        for tool_call in routing_decision.tools:
            tool = tools.get(tool_call.name)
            if tool is None:
                results.append(
                    ToolExecutionResult(
                        name=tool_call.name,
                        input=tool_call.suggested_input,
                        output="",
                        error=f"Tool is not registered: {tool_call.name}",
                    )
                )
                continue

            results.append(self._invoke_tool(tool_call, tool))
        return results

    def _invoke_tool(self, tool_call: ToolCallDecision, tool: Any) -> ToolExecutionResult:
        try:
            output = tool.invoke(tool_call.suggested_input)
        except Exception as exc:
            return ToolExecutionResult(
                name=tool_call.name,
                input=tool_call.suggested_input,
                output="",
                error=f"{type(exc).__name__}: {exc}",
            )

        return ToolExecutionResult(
            name=tool_call.name,
            input=tool_call.suggested_input,
            output=str(output),
        )

    def _build_clarifying_context(
        self,
        routing_decision: ToolRoutingDecision,
        missing_inputs: list[str],
    ) -> str:
        clarifying_question = routing_decision.clarifying_question.strip()
        if not clarifying_question:
            clarifying_question = f"请提醒用户补充工具调用所需参数：{'; '.join(missing_inputs)}。"

        return "\n".join(
            [
                "工具路由结果：需要使用工具，但缺少必要参数。",
                f"intent: {routing_decision.intent}",
                f"reason: {routing_decision.reason}",
                f"缺少参数：{'; '.join(missing_inputs)}",
                "",
                "回答要求：请不要编造参数或回答仓库事实。请用简洁中文提醒用户补充以下信息：",
                clarifying_question,
            ]
        )

    def _build_tool_context(
        self,
        routing_decision: ToolRoutingDecision,
        tool_results: list[ToolExecutionResult],
    ) -> str:
        blocks = [
            "工具路由结果：",
            f"- intent: {routing_decision.intent}",
            f"- reason: {routing_decision.reason}",
            "",
            "工具执行结果：",
        ]

        for index, result in enumerate(tool_results, start=1):
            blocks.extend(
                [
                    f"[{index}] tool: {result.name}",
                    f"input: {result.input}",
                ]
            )
            if result.error:
                blocks.append(f"error: {result.error}")
            else:
                blocks.extend(["output:", result.output])
            blocks.append("")

        blocks.extend(
            [
                "回答要求：请基于以上工具结果回答用户问题。回答必须引用具体文件路径；如果工具结果不足以支持结论，请明确说明还需要哪些信息。",
            ]
        )
        return "\n".join(blocks)

    def _load_repository_tools(self) -> dict[str, Any]:
        from src.tools import REPOSITORY_TOOLS

        return {tool.name: tool for tool in REPOSITORY_TOOLS}


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
