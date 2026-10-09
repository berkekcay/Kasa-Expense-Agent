"""Budget agent (owner: Agent dev #1) — sprint-1 stub.

TODO(sprint 3): budgets table + tools (set_budget, budget_status) so this agent can
set monthly limits per category and warn when spending approaches them.
"""

from google.adk.agents import Agent

from app.agents.common import GUARDRAILS, gemini_model

INSTRUCTION = f"""\
You are Kasa's budget agent. Budgets are not available yet (coming in a later sprint).
Tell the user briefly that budgets are coming soon and that, for now, they can ask
for spending reports (e.g. "how much did I spend on groceries this month?").

{GUARDRAILS}"""


def build_budget_agent() -> Agent:
    return Agent(
        name="budget_agent",
        model=gemini_model(),
        description="Monthly budgets and limits per category (coming soon).",
        instruction=INSTRUCTION,
    )
