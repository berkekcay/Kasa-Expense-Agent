"""Loop guard for every runner: a model that is stuck stops early with a clear note instead of
burning the whole turn (`MAX_LLM_CALLS`) or crashing it.

Small models get stuck in two ways: they call the same tool with the same arguments again
and again, or they keep retrying a tool that fails. Both cost a model call each and end with
"Stopped waiting". The guard counts per turn (one ADK invocation) and answers for the tool:

- the same call (tool + arguments) a fourth time: not run; the model is told to use the
  result it already has or explain the problem to the user;
- a tool that failed three times: not run again in this turn;
- a tool that raised an unexpected exception: the turn goes on with an error result, so the
  model can tell the user, instead of the whole answer failing.

The notes go back to the model as tool results, the same `{"status": "error"}` shape the
tools use, and are logged so a stuck turn is visible in the server log.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any

from google.adk.plugins.base_plugin import BasePlugin

log = logging.getLogger(__name__)

SAME_CALL_LIMIT = 3  # the 4th identical call in one turn is refused
ERROR_LIMIT = 3  # after 3 failures of one tool in one turn it is not run again


def _key(name: str, args: dict[str, Any]) -> str:
    return name + json.dumps(args, sort_keys=True, default=str, ensure_ascii=False)


class LoopGuardPlugin(BasePlugin):
    def __init__(self) -> None:
        super().__init__(name="kasa_loop_guard")
        self._calls: dict[str, Counter[str]] = {}
        self._errors: dict[str, Counter[str]] = {}

    def _turn(self, tool_context) -> tuple[Counter[str], Counter[str]]:
        turn = tool_context.invocation_id
        return self._calls.setdefault(turn, Counter()), self._errors.setdefault(turn, Counter())

    async def before_tool_callback(self, *, tool, tool_args, tool_context) -> dict | None:
        calls, errors = self._turn(tool_context)
        if errors[tool.name] >= ERROR_LIMIT:
            log.warning("loop guard: %s failed %d times, not running it again", tool.name, errors[tool.name])
            return {
                "status": "error",
                "error": f"{tool.name} failed {errors[tool.name]} times in this answer. Do not call it "
                "again; tell the user what went wrong and what they can do.",
            }
        key = _key(tool.name, tool_args)
        if calls[key] >= SAME_CALL_LIMIT:
            log.warning("loop guard: %s called %d times with the same arguments", tool.name, calls[key])
            return {
                "status": "error",
                "error": f"You already called {tool.name} with these exact arguments {calls[key]} times "
                "in this answer. Use the result you already have, or explain the problem to the user.",
            }
        calls[key] += 1
        return None

    async def after_tool_callback(self, *, tool, tool_args, tool_context, result) -> dict | None:
        if isinstance(result, dict) and result.get("status") == "error":
            self._turn(tool_context)[1][tool.name] += 1
        return None

    async def on_tool_error_callback(self, *, tool, tool_args, tool_context, error) -> dict | None:
        log.exception("tool %s raised", tool.name, exc_info=error)
        self._turn(tool_context)[1][tool.name] += 1
        return {
            "status": "error",
            "error": f"{tool.name} failed unexpectedly. Tell the user it did not work and suggest "
            "trying again later; do not guess the result.",
        }

    async def after_run_callback(self, *, invocation_context) -> None:
        self._calls.pop(invocation_context.invocation_id, None)
        self._errors.pop(invocation_context.invocation_id, None)
