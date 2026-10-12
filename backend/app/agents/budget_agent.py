"""Budget agent (owner: track MONEY): budgets, alerts, subscriptions, currency conversion."""

from google.adk.agents import Agent

from app.agents.common import GUARDRAILS, chat_model, with_today
from app.agents.tools.budget_tools import (
    convert_currency,
    get_budget_status,
    list_subscriptions,
    set_budget,
)

INSTRUCTION = f"""\
You are Kasa's budget agent. You help the user plan spending.

- To create or change a monthly limit, call `set_budget` (empty category = overall budget).
- "How am I doing", "can I still spend", "budget left": call `get_budget_status`.
- Recurring charges (Netflix, Spotify, gym): call `list_subscriptions`.
- Exchange rates or "how much is 50 EUR": call `convert_currency` (TCMB rates).
If a tool says a feature is not available yet, say so briefly.

{GUARDRAILS}"""


def build_budget_agent() -> Agent:
    return Agent(
        name="budget_agent",
        model=chat_model(),
        description=(
            "Monthly budgets and limits per category, budget status/alerts, recurring "
            "subscriptions, and currency conversion with TCMB exchange rates (kur)."
        ),
        instruction=with_today(INSTRUCTION),
        tools=[set_budget, get_budget_status, list_subscriptions, convert_currency],
    )
