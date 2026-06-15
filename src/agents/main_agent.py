"""Main agent orchestration for repository questions."""

from __future__ import annotations

import json
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
    routing_decisions: list[ToolRoutingDecision] = field(default_factory=list)


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
        max_tool_rounds: int = 3,
    ):
        if max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be at least 1.")

        self.routing_agent = routing_agent
        self.answer_chain = answer_chain
        self.tools = tools
        self.max_tool_rounds = max_tool_rounds

    def run(self, user_input: str) -> CoderAgentResult:
        """Route the request, run tools when needed, and return the final answer."""
        self._validate_user_input(user_input)

        routing_decisions, context, tool_results = self._route_until_ready(user_input)
        answer = self.answer_chain.invoke(self._build_answer_input(user_input, context))
        return CoderAgentResult(
            input=user_input,
            answer=answer,
            routing_decision=routing_decisions[-1],
            routing_decisions=routing_decisions,
            tool_results=tool_results,
        )

    def stream(self, user_input: str) -> Iterator[str]:
        """Route the request, run tools when needed, and stream the final answer."""
        self._validate_user_input(user_input)

        _, context, _ = self._route_until_ready(user_input)
        yield from self.answer_chain.stream(self._build_answer_input(user_input, context))

    def _validate_user_input(self, user_input: str) -> None:
        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError("user_input must be a non-empty string.")

    def _route_until_ready(
        self,
        user_input: str,
    ) -> tuple[list[ToolRoutingDecision], str, list[ToolExecutionResult]]:
        routing_decisions: list[ToolRoutingDecision] = []
        tool_results: list[ToolExecutionResult] = []
        executed_calls: set[str] = set()
        context = ""

        for round_index in range(1, self.max_tool_rounds + 1):
            routing_input = self._build_routing_input(user_input, context, round_index, executed_calls)
            routing_decision = self.routing_agent.route(routing_input)
            routing_decisions.append(routing_decision)

            if not routing_decision.needs_tools:
                return routing_decisions, context, tool_results

            missing_inputs = self._find_missing_inputs(routing_decision)
            if missing_inputs:
                context = self._build_clarifying_context(routing_decision, missing_inputs)
                return routing_decisions, context, tool_results

            new_tool_calls = self._select_new_tool_calls(routing_decision, executed_calls)
            if not new_tool_calls:
                context = self._build_duplicate_tool_context(routing_decision, tool_results)
                return routing_decisions, context, tool_results

            round_results = self._execute_tool_calls(new_tool_calls, executed_calls)
            tool_results.extend(round_results)
            context = self._build_tool_context(routing_decision, tool_results)

        context = self._build_max_rounds_context(routing_decisions, tool_results)
        return routing_decisions, context, tool_results

    def _build_answer_input(self, user_input: str, context: str) -> dict[str, str]:
        if context:
            return {"input": user_input, "context": context}

        return {"input": user_input}

    def _build_routing_input(
        self,
        user_input: str,
        context: str,
        round_index: int,
        executed_calls: set[str],
    ) -> str:
        if not context:
            return user_input

        return "\n".join(
            [
                "用户原始问题：",
                user_input,
                "",
                f"当前是第 {round_index} 轮工具路由。",
                "",
                "已获得的工具上下文：",
                context,
                "",
                "已经执行过的工具调用签名：",
                "\n".join(sorted(executed_calls)) if executed_calls else "无",
                "",
                "请判断是否还需要继续调用其他工具。",
                "如果已有上下文足够回答用户原始问题，请返回 needs_tools=false。",
                "如果还缺信息，只返回下一轮需要调用的工具，不要重复调用已经执行过的工具。",
            ]
        )

    def _find_missing_inputs(self, routing_decision: ToolRoutingDecision) -> list[str]:
        missing: list[str] = []
        for tool_call in routing_decision.tools:
            required_keys = REQUIRED_TOOL_INPUTS.get(tool_call.name, ())
            missing_keys = [key for key in required_keys if key not in tool_call.suggested_input]
            if missing_keys:
                missing.append(f"{tool_call.name}: {', '.join(missing_keys)}")
        return missing

    def _select_new_tool_calls(
        self,
        routing_decision: ToolRoutingDecision,
        executed_calls: set[str],
    ) -> list[ToolCallDecision]:
        return [
            tool_call
            for tool_call in routing_decision.tools
            if self._tool_call_key(tool_call) not in executed_calls
        ]

    def _execute_tool_calls(
        self,
        tool_calls: list[ToolCallDecision],
        executed_calls: set[str],
    ) -> list[ToolExecutionResult]:
        tools = self.tools if self.tools is not None else self._load_repository_tools()
        results: list[ToolExecutionResult] = []
        for tool_call in tool_calls:
            executed_calls.add(self._tool_call_key(tool_call))
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

    def _tool_call_key(self, tool_call: ToolCallDecision) -> str:
        input_text = json.dumps(tool_call.suggested_input, sort_keys=True, ensure_ascii=False)
        return f"{tool_call.name}:{input_text}"

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

    def _build_duplicate_tool_context(
        self,
        routing_decision: ToolRoutingDecision,
        tool_results: list[ToolExecutionResult],
    ) -> str:
        context = self._build_tool_context(routing_decision, tool_results) if tool_results else ""
        blocks = []
        if context:
            blocks.append(context)
            blocks.append("")

        blocks.extend(
            [
                "循环式工具路由已停止：路由器要求的工具调用都已经执行过。",
                "回答要求：请基于已有工具结果回答用户问题；如果已有结果不足，请明确说明还缺少哪些信息，不要重复请求相同工具。",
            ]
        )
        return "\n".join(blocks)

    def _build_max_rounds_context(
        self,
        routing_decisions: list[ToolRoutingDecision],
        tool_results: list[ToolExecutionResult],
    ) -> str:
        last_decision = routing_decisions[-1]
        context = self._build_tool_context(last_decision, tool_results) if tool_results else ""
        blocks = []
        if context:
            blocks.append(context)
            blocks.append("")

        blocks.extend(
            [
                f"循环式工具路由已达到最大轮数：{self.max_tool_rounds}。",
                "回答要求：请基于目前已经获得的工具结果回答用户问题；如果信息仍不足，请说明还需要继续读取哪些文件或运行哪些检索。",
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
    max_tool_rounds: int = 3,
) -> CoderAgent:
    """Create the main coder agent with one shared model client."""
    if model is None:
        from src.models import get_ali_model_client

        model = get_ali_model_client(temperature=temperature)

    routing_agent = get_tool_routing_agent(model=model)
    if answer_chain is None:
        answer_chain = get_answer_chain(model=model)

    return CoderAgent(
        routing_agent=routing_agent,
        answer_chain=answer_chain,
        max_tool_rounds=max_tool_rounds,
    )
