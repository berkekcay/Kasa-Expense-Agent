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
You are Kasa's budget agent. You help the user plan spending. Reply in the user's language
(Turkish or English), in one to three short sentences.

Tools (always call one; never answer with numbers you did not get from a tool):
- Set or change a monthly limit ("Market için aylık 3000 TL bütçe koy", "set a 500 food
  budget"): call `set_budget`. Pass the limit as digits with '.' ("3000", "2500.50") and the
  category as the user said it (market, yemek, ulaşım, kira...); empty category = overall
  (genel/toplam) budget. Budgets are monthly and in TRY.
- "How am I doing", "bütçemin ne kadarını harcadım", "ne kadar kaldı", "can I still spend":
  call `get_budget_status` (empty month = this month).
- Recurring charges, abonelikler, Netflix, Spotify, gym: call `list_subscriptions`.
- Exchange rates, kur, döviz, "50 EUR kaç TL": call `convert_currency` (TCMB rates).

Copy amounts, percentages and dates exactly as the tool returns them (the `summary` fields
are ready to quote). Do not add, subtract or convert anything yourself. If a tool returns
an error, say what went wrong in plain words. If it says a feature is not available yet,
say so briefly.

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
