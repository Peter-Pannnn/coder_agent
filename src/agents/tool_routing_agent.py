"""Agent for producing structured tool routing decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import Runnable, RunnableLambda

# 路由模型只能返回这些意图，避免后续 Agent 处理未知分支。
ALLOWED_INTENTS = {
    "locate_code",
    "explain_code",
    "plan_change",
    "run_tests",
    "index_repository",
    "answer_general",
    "unknown",
}

# 工具名必须和 src.tools 对外导出的工具名称保持一致。
ALLOWED_TOOLS = {
    "list_files",
    "read_file",
    "search_code",
    "index_repository",
    "retrieve_context",
}


@dataclass(frozen=True)
class ToolCallDecision:
    """A single tool candidate selected by the routing model."""

    name: str
    purpose: str
    priority: int
    suggested_input: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolRoutingDecision:
    """Structured decision returned by the tool routing agent."""

    intent: str
    needs_tools: bool
    confidence: float
    reason: str
    tools: list[ToolCallDecision]
    answer_without_tools: bool
    clarifying_question: str = ""


class ToolRoutingDecisionError(ValueError):
    """Raised when a model response cannot be parsed as a routing decision."""


def _extract_content(response: Any) -> str:
    # 兼容 LangChain 消息对象和测试中直接传入字符串的两种情况。
    if isinstance(response, str):
        return response

    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content

    raise ToolRoutingDecisionError("Model response does not contain text content.")


def _strip_json_fence(text: str) -> str:
    # 模型偶尔会把 JSON 包在 ```json ... ``` 中，这里先去掉代码块外壳。
    text = text.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()

    return text


def parse_tool_routing_decision(response: Any) -> ToolRoutingDecision:
    """Parse and validate a model response into a routing decision."""
    # JsonOutputParser 已经会输出 dict；单独测试解析函数时也允许传字符串。
    if isinstance(response, dict):
        return _parse_tool_routing_payload(response)

    text = _strip_json_fence(_extract_content(response))

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ToolRoutingDecisionError(f"Invalid routing JSON: {exc}") from exc

    return _parse_tool_routing_payload(payload)


def _parse_tool_routing_payload(payload: Any) -> ToolRoutingDecision:
    """Validate a decoded routing payload and convert it to a decision."""
    # 这里做业务层校验，不只依赖 JSON 是否能被解析。
    if not isinstance(payload, dict):
        raise ToolRoutingDecisionError("Routing decision must be a JSON object.")

    intent = payload.get("intent")
    if intent not in ALLOWED_INTENTS:
        raise ToolRoutingDecisionError(f"Invalid intent: {intent!r}.")

    needs_tools = payload.get("needs_tools")
    if not isinstance(needs_tools, bool):
        raise ToolRoutingDecisionError("needs_tools must be a boolean.")

    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ToolRoutingDecisionError("confidence must be a number.")
    confidence = float(confidence)
    if not 0 <= confidence <= 1:
        raise ToolRoutingDecisionError("confidence must be between 0 and 1.")

    reason = payload.get("reason")
    if not isinstance(reason, str):
        raise ToolRoutingDecisionError("reason must be a string.")

    answer_without_tools = payload.get("answer_without_tools")
    if not isinstance(answer_without_tools, bool):
        raise ToolRoutingDecisionError("answer_without_tools must be a boolean.")

    clarifying_question = payload.get("clarifying_question", "")
    if not isinstance(clarifying_question, str):
        raise ToolRoutingDecisionError("clarifying_question must be a string.")

    raw_tools = payload.get("tools")
    if not isinstance(raw_tools, list):
        raise ToolRoutingDecisionError("tools must be a list.")

    # 按 priority 排序，调用方可以直接按列表顺序执行工具。
    tools = [_parse_tool_call_decision(item) for item in raw_tools]
    tools = sorted(tools, key=lambda tool: tool.priority)

    if needs_tools and not tools:
        raise ToolRoutingDecisionError("tools cannot be empty when needs_tools is true.")

    if not needs_tools and tools:
        raise ToolRoutingDecisionError("tools must be empty when needs_tools is false.")

    return ToolRoutingDecision(
        intent=intent,
        needs_tools=needs_tools,
        confidence=confidence,
        reason=reason,
        tools=tools,
        answer_without_tools=answer_without_tools,
        clarifying_question=clarifying_question,
    )


def _parse_tool_call_decision(payload: Any) -> ToolCallDecision:
    if not isinstance(payload, dict):
        raise ToolRoutingDecisionError("Each tool decision must be a JSON object.")

    name = payload.get("name")
    if name not in ALLOWED_TOOLS:
        raise ToolRoutingDecisionError(f"Invalid tool name: {name!r}.")

    purpose = payload.get("purpose")
    if not isinstance(purpose, str):
        raise ToolRoutingDecisionError("tool purpose must be a string.")

    priority = payload.get("priority")
    if not isinstance(priority, int) or isinstance(priority, bool) or priority < 1:
        raise ToolRoutingDecisionError("tool priority must be a positive integer.")

    suggested_input = payload.get("suggested_input", {})
    if not isinstance(suggested_input, dict):
        raise ToolRoutingDecisionError("tool suggested_input must be an object.")

    return ToolCallDecision(
        name=name,
        purpose=purpose,
        priority=priority,
        suggested_input=suggested_input,
    )


class ToolRoutingAgent:
    """LangChain-based agent that returns a validated tool routing decision."""

    def __init__(self, model: Runnable, prompt: Runnable | None = None):
        self.model = model
        self.prompt = prompt
        self._chain: Runnable | None = None

    def route(self, user_input: str) -> ToolRoutingDecision:
        """Return a structured decision for the user's request."""
        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError("user_input must be a non-empty string.")

        return self.as_chain().invoke({"input": user_input})

    def as_chain(self) -> Runnable:
        """Return the LangChain runnable used by this agent."""
        # 链是无状态的，第一次构建后缓存起来，避免每次 route 都重复组装。
        if self._chain is None:
            self._chain = self._build_chain()

        return self._chain

    def _build_chain(self) -> Runnable:
        # LCEL pipeline:
        # prompt 生成路由提示词 -> model 输出 JSON -> JsonOutputParser 转 dict
        # -> RunnableLambda 做字段校验并转换为 ToolRoutingDecision。
        return (
            self._get_prompt()
            | self.model
            | JsonOutputParser()
            | RunnableLambda(parse_tool_routing_decision)
        )

    def _get_prompt(self) -> Runnable:
        if self.prompt is not None:
            return self.prompt

        from src.prompt import get_tool_routing_chat_prompt

        return get_tool_routing_chat_prompt()


def get_tool_routing_agent(model: Any | None = None) -> ToolRoutingAgent:
    """Create a tool routing agent with a deterministic default model."""
    if model is None:
        from src.models import get_ali_model_client

        # 工具路由需要稳定输出结构化 JSON，所以默认使用低温度。
        model = get_ali_model_client(temperature=0.0)

    return ToolRoutingAgent(model=model)
