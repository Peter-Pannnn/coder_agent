"""Main agent orchestration for repository questions."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable

from src.memory import ChromaLongTermMemory, SQLiteShortTermMemory

from .answer_chain import get_answer_chain
from .tool_routing_agent import ToolCallDecision, ToolRoutingAgent, ToolRoutingDecision, get_tool_routing_agent


REQUIRED_TOOL_INPUTS: dict[str, tuple[str, ...]] = {
    "read_file": ("file_path",),
    "search_code": ("query",),
    "index_repository": ("target_path",),
    "retrieve_context": ("query",),
}

LONG_TERM_MEMORY_TRIGGERS = (
    "请记住",
    "记住",
    "以后请",
    "以后默认",
    "默认用",
    "我的偏好",
    "我偏好",
    "我的习惯",
    "我习惯",
)


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
    long_term_memory_context: str = ""
    long_term_memory_write: str = ""


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
        memory: SQLiteShortTermMemory | None = None,
        long_term_memory: ChromaLongTermMemory | None = None,
        session_id: str = "default",
        user_id: str = "default",
        answer_memory_messages: int | None = None,
        routing_memory_messages: int = 4,
        long_term_memory_k: int = 4,
        auto_save_long_term_memory: bool = True,
    ):
        if max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be at least 1.")
        if answer_memory_messages is not None and answer_memory_messages < 0:
            raise ValueError("answer_memory_messages must be non-negative.")
        if routing_memory_messages < 0:
            raise ValueError("routing_memory_messages must be non-negative.")
        if long_term_memory_k < 0:
            raise ValueError("long_term_memory_k must be non-negative.")
        if not user_id.strip():
            raise ValueError("user_id must be a non-empty string.")

        self.routing_agent = routing_agent
        self.answer_chain = answer_chain
        self.tools = tools
        self.max_tool_rounds = max_tool_rounds
        self.memory = memory
        self.long_term_memory = long_term_memory
        self.session_id = session_id
        self.user_id = user_id
        self.answer_memory_messages = answer_memory_messages
        self.routing_memory_messages = routing_memory_messages
        self.long_term_memory_k = long_term_memory_k
        self.auto_save_long_term_memory = auto_save_long_term_memory

    def run(self, user_input: str) -> CoderAgentResult:
        """Route the request, run tools when needed, and return the final answer."""
        self._validate_user_input(user_input)

        answer_history = self._load_memory_messages(self.answer_memory_messages)
        long_term_memory_write = self._maybe_store_long_term_memory(user_input)
        long_term_memory_context = self._render_long_term_memory_context(user_input)
        routing_decisions, context, tool_results = self._route_until_ready(user_input)
        answer_context = self._build_answer_context(
            tool_context=context,
            long_term_memory_context=long_term_memory_context,
            long_term_memory_write=long_term_memory_write,
        )
        answer = self.answer_chain.invoke(self._build_answer_input(user_input, answer_context, answer_history))
        self._remember_exchange(user_input, answer)
        return CoderAgentResult(
            input=user_input,
            answer=answer,
            routing_decision=routing_decisions[-1],
            routing_decisions=routing_decisions,
            tool_results=tool_results,
            long_term_memory_context=long_term_memory_context,
            long_term_memory_write=long_term_memory_write,
        )

    def stream(self, user_input: str) -> Iterator[str]:
        """Route the request, run tools when needed, and stream the final answer."""
        self._validate_user_input(user_input)

        long_term_memory_write = self._maybe_store_long_term_memory(user_input)
        long_term_memory_context = self._render_long_term_memory_context(user_input)
        _, context, _ = self._route_until_ready(user_input)
        answer_history = self._load_memory_messages(self.answer_memory_messages)
        answer_context = self._build_answer_context(
            tool_context=context,
            long_term_memory_context=long_term_memory_context,
            long_term_memory_write=long_term_memory_write,
        )
        chunks: list[str] = []
        for chunk in self.answer_chain.stream(self._build_answer_input(user_input, answer_context, answer_history)):
            chunks.append(chunk)
            yield chunk

        self._remember_exchange(user_input, "".join(chunks))

    def remember_preference(
        self,
        content: str,
        category: str = "preference",
        source: str = "manual",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Persist one user preference into long-term personal memory."""
        if self.long_term_memory is None:
            raise ValueError("long_term_memory is not configured.")

        return self.long_term_memory.add_memory(
            content=content,
            user_id=self.user_id,
            category=category,
            source=source,
            metadata=metadata,
        )

    def clear_long_term_memory(self) -> int:
        """Clear long-term personal memory for the current user."""
        if self.long_term_memory is None:
            return 0

        return self.long_term_memory.clear(user_id=self.user_id)

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
        routing_history = self._render_memory(self.routing_memory_messages)

        for round_index in range(1, self.max_tool_rounds + 1):
            routing_input = self._build_routing_input(
                user_input,
                context,
                round_index,
                executed_calls,
                routing_history,
            )
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

    def _build_answer_input(
        self,
        user_input: str,
        context: str,
        history: list[BaseMessage],
    ) -> dict[str, Any]:
        answer_input: dict[str, Any] = {"input": user_input}
        if history:
            answer_input["history"] = history
        if context:
            answer_input["context"] = context

        return answer_input

    def _build_answer_context(
        self,
        tool_context: str,
        long_term_memory_context: str,
        long_term_memory_write: str,
    ) -> str:
        blocks = []
        if long_term_memory_write:
            blocks.extend(
                [
                    "长期个人记忆写入结果：",
                    long_term_memory_write,
                ]
            )
        if long_term_memory_context:
            blocks.append(long_term_memory_context)
        if tool_context:
            blocks.append(tool_context)

        return "\n\n".join(blocks)

    def _build_routing_input(
        self,
        user_input: str,
        context: str,
        round_index: int,
        executed_calls: set[str],
        history: str,
    ) -> str:
        if not context and not history:
            return user_input

        blocks = []
        if history:
            blocks.extend(
                [
                    "历史对话：",
                    history,
                    "",
                ]
            )

        if not context:
            blocks.extend(["用户原始问题：", user_input])
            return "\n".join(blocks)

        blocks.extend(
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
        return "\n".join(blocks)

    def _render_memory(self, limit: int | None) -> str:
        if self.memory is None:
            return ""
        if limit is not None and limit <= 0:
            return ""

        return self.memory.render_recent(session_id=self.session_id, limit=limit)

    def _load_memory_messages(self, limit: int | None) -> list[BaseMessage]:
        if self.memory is None:
            return []
        if limit is not None and limit <= 0:
            return []

        return self.memory.load_recent_chat_messages(session_id=self.session_id, limit=limit)

    def _render_long_term_memory_context(self, user_input: str) -> str:
        if self.long_term_memory is None or self.long_term_memory_k <= 0:
            return ""

        try:
            return self.long_term_memory.render_relevant(
                query=user_input,
                user_id=self.user_id,
                k=self.long_term_memory_k,
            )
        except Exception:
            return ""

    def _maybe_store_long_term_memory(self, user_input: str) -> str:
        if not self.auto_save_long_term_memory or self.long_term_memory is None:
            return ""

        memory_content = self._extract_preference_memory(user_input)
        if not memory_content:
            return ""

        try:
            memory_id = self.remember_preference(
                memory_content,
                category="preference",
                source="conversation",
                metadata={"session_id": self.session_id},
            )
        except Exception as exc:
            return f"写入失败：{type(exc).__name__}: {exc}"

        return "\n".join(
            [
                f"已保存用户长期偏好：{memory_content}",
                f"memory_id: {memory_id}",
            ]
        )

    def _extract_preference_memory(self, user_input: str) -> str:
        text = user_input.strip()
        if not any(trigger in text for trigger in LONG_TERM_MEMORY_TRIGGERS):
            return ""

        cleaned = text
        for prefix in ("请记住", "记住"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip(" ：:，,。")
                break

        return cleaned or text

    def _remember_exchange(self, user_input: str, answer: str) -> None:
        if self.memory is None:
            return

        self.memory.add_message(self.session_id, "user", user_input)
        self.memory.add_message(self.session_id, "assistant", answer)

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
    max_tool_rounds: int = 3,
    session_id: str = "default",
    user_id: str = "default",
    routing_memory_messages: int = 4,
) -> CoderAgent:
    """Create the main coder agent with default chains and memory."""
    if model is None:
        from src.models import get_ali_model_client

        model = get_ali_model_client(temperature=temperature)

    routing_agent = get_tool_routing_agent(model=model)
    answer_chain = get_answer_chain(model=model)
    memory = SQLiteShortTermMemory()
    long_term_memory = ChromaLongTermMemory()

    return CoderAgent(
        routing_agent=routing_agent,
        answer_chain=answer_chain,
        max_tool_rounds=max_tool_rounds,
        memory=memory,
        long_term_memory=long_term_memory,
        session_id=session_id,
        user_id=user_id,
        routing_memory_messages=routing_memory_messages,
    )
