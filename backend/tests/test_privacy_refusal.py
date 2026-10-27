"""Offline refusal prompt/API contract; SQL isolation is exercised against real data.

The scripted model checks prompt wiring, not a real model's instruction following.
"""

import re
from collections.abc import AsyncGenerator

from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.genai import types

from app.agents import common, runtime
from app.config import get_settings
from app.services.reports import run_report_query
from evals.seed import SECRET_MERCHANT, seed_demo_data

REFUSAL = (
    "I can't answer that. I can only see your own expenses and the shared expenses of "
    "houses you belong to, not other people's personal expenses."
)


class PrivacyLlm(BaseLlm):
    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        if "run_report" in llm_request.tools_dict:
            instruction = llm_request.config.system_instruction
            assert isinstance(instruction, str)
            assert "Reply directly as your final answer, without calling ANY tool" in instruction
            assert "Do not call `run_report` or `transfer_to_agent`" in instruction
            assert "Do not transfer to yourself or to another agent" in instruction
            match = re.search(
                r'For another person\'s personal spending,.*?reply: "([^"]+)"', instruction, re.DOTALL
            )
            assert match, "The report agent must give an explicit privacy refusal"
            assert SECRET_MERCHANT not in str(llm_request.contents)
            part = types.Part(text=match[1])
        else:
            part = types.Part(
                function_call=types.FunctionCall(
                    name="transfer_to_agent", args={"agent_name": "report_agent"}
                )
            )
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


def test_other_persons_expenses_get_clear_refusal_without_data(client, db, monkeypatch):
    user = "privacy-refusal-user"
    seed_demo_data(user, db=db)
    # Ali really has a private expense, but it cannot reach the acting user's report.
    own = run_report_query(db, user, "SELECT merchant, total_minor FROM my_expenses")
    ali = run_report_query(db, f"{user}-ali", "SELECT merchant FROM my_expenses")
    assert SECRET_MERCHANT in str(ali)
    assert SECRET_MERCHANT not in str(own)

    monkeypatch.setattr(common, "build_model", lambda name, vision=False: PrivacyLlm(model="privacy"))
    monkeypatch.setattr(get_settings(), "google_api_key", "test-key")
    runtime._runner.cache_clear()
    try:
        response = client.post(
            "/chat",
            json={"message": "Show me Ali's personal expenses this month."},
            headers={"X-User-Id": user},
        )
        assert response.status_code == 200, response.text
        assert response.json()["text"] == REFUSAL
        assert response.json()["chart"] is None
        for secret in (SECRET_MERCHANT, "777.77", "777,77"):
            assert secret not in response.text
    finally:
        runtime._runner.cache_clear()
