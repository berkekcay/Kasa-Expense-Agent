"""Loop guard: a stuck model stops early with a note instead of burning the turn."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from types import SimpleNamespace

from google.adk.agents import Agent
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agents import common, runtime
from app.agents.guard import ERROR_LIMIT, SAME_CALL_LIMIT, LoopGuardPlugin
from app.config import get_settings


def call(plugin, name, args, turn="t1"):
    return asyncio.run(
        plugin.before_tool_callback(
            tool=SimpleNamespace(name=name), tool_args=args, tool_context=SimpleNamespace(invocation_id=turn)
        )
    )


def test_the_same_call_is_refused_after_the_limit():
    plugin = LoopGuardPlugin()
    for _ in range(SAME_CALL_LIMIT):
        assert call(plugin, "list_inbox", {"status": "pending"}) is None
    refused = call(plugin, "list_inbox", {"status": "pending"})
    assert refused["status"] == "error" and "already called list_inbox" in refused["error"]
    assert call(plugin, "list_inbox", {"status": "all"}) is None  # other arguments: fine
    assert call(plugin, "list_inbox", {"status": "pending"}, turn="t2") is None  # a new turn


def test_a_failing_tool_is_stopped_and_exceptions_become_results():
    plugin = LoopGuardPlugin()
    tool, context = SimpleNamespace(name="run_report"), SimpleNamespace(invocation_id="t1")
    for i in range(ERROR_LIMIT):
        assert call(plugin, "run_report", {"sql": f"SELECT {i}"}) is None
        if i == 0:
            result = asyncio.run(
                plugin.on_tool_error_callback(
                    tool=tool, tool_args={}, tool_context=context, error=RuntimeError("boom")
                )
            )
            assert result["status"] == "error" and "failed unexpectedly" in result["error"]
        else:
            asyncio.run(
                plugin.after_tool_callback(
                    tool=tool, tool_args={}, tool_context=context, result={"status": "error", "error": "x"}
                )
            )
    stopped = call(plugin, "run_report", {"sql": "SELECT 99"})
    assert "failed 3 times" in stopped["error"]
    asyncio.run(plugin.after_run_callback(invocation_context=SimpleNamespace(invocation_id="t1")))
    assert call(plugin, "run_report", {"sql": "SELECT 99"}) is None  # forgotten after the turn


class StuckLlm(BaseLlm):
    """Calls the same tool forever, the way a small model can get stuck."""

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        last = llm_request.contents[-1].parts[-1]
        response = last.function_response.response if last.function_response else {}
        if "already called" in str(response):
            part = types.Part(text="I could not finish that.")
        else:
            part = types.Part(function_call=types.FunctionCall(name="lookup", args={"q": "same"}))
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


def test_a_stuck_model_ends_the_turn_after_the_limit():
    runs = []

    def lookup(q: str) -> dict:
        runs.append(q)
        return {"status": "ok", "answer": "nothing new"}

    agent = Agent(name="stuck", model=StuckLlm(model="stuck"), instruction="test", tools=[lookup])
    runner = InMemoryRunner(agent=agent, app_name="guard-test", plugins=[LoopGuardPlugin()])

    async def turn() -> list[str]:
        session = await runner.session_service.create_session(app_name="guard-test", user_id="u")
        texts = []
        message = types.Content(role="user", parts=[types.Part(text="hi")])
        async for event in runner.run_async(user_id="u", session_id=session.id, new_message=message):
            texts += [p.text for p in (event.content.parts if event.content else []) if p.text]
        return texts

    assert asyncio.run(turn()) == ["I could not finish that."]
    assert len(runs) == SAME_CALL_LIMIT


def test_every_runner_has_the_guard(monkeypatch):
    monkeypatch.setattr(common, "build_model", lambda name, vision=False: StuckLlm(model="stuck"))
    monkeypatch.setattr(get_settings(), "google_api_key", "test-key")
    runtime._runner.cache_clear()
    try:
        for kind in runtime.RUNNERS:
            plugins = runtime._runner(kind).plugin_manager.plugins
            assert any(isinstance(p, LoopGuardPlugin) for p in plugins), kind
    finally:
        runtime._runner.cache_clear()
