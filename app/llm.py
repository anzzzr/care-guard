"""LLM layer: one small interface, a real Gemini client, and a scripted fake for tests.

The agent only sees these provider-neutral types, so swapping Gemini for another
model means writing one new class with a `generate` method.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import httpx2
from google import genai
from google.genai import errors, types

# One Gemini request may take at most this long. Without it a stalled call hangs the request.
REQUEST_TIMEOUT_MS = 30_000


class LLMError(Exception):
    """The LLM provider failed (bad key, quota, outage). Callers need not know which provider."""


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    id: str | None = None


@dataclass
class ToolResult:
    call: ToolCall
    result: dict[str, Any]


@dataclass
class Message:
    role: Literal["user", "assistant", "tool"]
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    # The provider's own copy of an assistant turn. Gemini needs it sent back
    # unchanged because it carries hidden "thought signatures".
    raw: Any = None


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    raw: Any = None


class LLMClient(Protocol):
    def generate(self, system: str, messages: list[Message], tools: list[dict]) -> LLMResponse:
        """Send the conversation so far; get back text and/or tool calls."""
        ...


class GeminiClient:
    def __init__(self, api_key: str, model: str) -> None:
        # Retry short-lived errors (rate limit, "high demand") a few times before giving up.
        retry = types.HttpRetryOptions(
            attempts=4, initial_delay=1.0, max_delay=8.0, http_status_codes=[429, 500, 503, 504]
        )
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(retry_options=retry, timeout=REQUEST_TIMEOUT_MS),
        )
        self._model = model

    def generate(self, system: str, messages: list[Message], tools: list[dict]) -> LLMResponse:
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t["name"],
                            description=t["description"],
                            parameters_json_schema=t["parameters"],
                        )
                        for t in tools
                    ]
                )
            ],
            # We run tools ourselves, in agent.py, so member_id stays in our code.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        try:
            response = self._client.models.generate_content(
                model=self._model, contents=[_to_gemini(m) for m in messages], config=config
            )
        except errors.APIError as exc:
            raise LLMError(f"Gemini error {exc.code}: {exc.message}") from exc
        except httpx2.TimeoutException as exc:
            raise LLMError(f"Gemini timed out after {REQUEST_TIMEOUT_MS // 1000}s") from exc
        content = response.candidates[0].content if response.candidates else None
        parts = (content.parts if content else None) or []
        usage = response.usage_metadata
        return LLMResponse(
            text="".join(p.text for p in parts if p.text and not p.thought),
            tool_calls=[
                ToolCall(
                    name=p.function_call.name,
                    args=dict(p.function_call.args or {}),
                    id=p.function_call.id,
                )
                for p in parts
                if p.function_call
            ],
            tokens_in=(usage.prompt_token_count or 0) if usage else 0,
            tokens_out=((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0))
            if usage
            else 0,
            raw=content,
        )


def _to_gemini(message: Message) -> types.Content:
    if message.role == "user":
        return types.Content(role="user", parts=[types.Part(text=message.text)])
    if message.role == "assistant":
        if message.raw is not None:
            return message.raw
        parts = [types.Part(text=message.text)] if message.text else []
        parts += [
            types.Part(function_call=types.FunctionCall(id=c.id, name=c.name, args=c.args))
            for c in message.tool_calls
        ]
        return types.Content(role="model", parts=parts)
    return types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=r.call.id, name=r.call.name, response=r.result
                )
            )
            for r in message.tool_results
        ],
    )


class FakeLLMClient:
    """Returns scripted responses in order and records every call. No network."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[list[Message]] = []

    def generate(self, system: str, messages: list[Message], tools: list[dict]) -> LLMResponse:
        self.calls.append(list(messages))
        if not self._responses:
            raise AssertionError("FakeLLMClient ran out of scripted responses")
        return self._responses.pop(0)
