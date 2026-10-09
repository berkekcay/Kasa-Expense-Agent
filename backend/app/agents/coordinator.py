"""Coordinator (owner: Agent dev #1): routes each chat message to the right specialist.

ADK gives an Agent with `sub_agents` a built-in `transfer_to_agent` tool; the LLM decides
*which* agent handles the request, and the specialists' tools do all the money math.
"""

from google.adk.agents import Agent

from app.agents.budget_agent import build_budget_agent
from app.agents.common import GUARDRAILS, gemini_model
from app.agents.house_agent import build_house_agent
from app.agents.receipt_agent import build_receipt_agent
from app.agents.report_agent import build_report_agent

INSTRUCTION = f"""\
You are Kasa, a money assistant for students. Route every request to a specialist:
- receipt_agent: saving a purchase/expense, receipt questions, listing recent expenses.
- house_agent: shared flat (house) bills, splitting, balances, who owes whom, settling up.
- report_agent: questions about spending totals, categories, trends, charts.
- budget_agent: budgets and spending limits.
Greet or answer small talk yourself in one sentence; otherwise transfer.

{GUARDRAILS}"""


def build_coordinator(sql_dialect: str) -> Agent:
    return Agent(
        name="kasa_coordinator",
        model=gemini_model(),
        description="Kasa root agent that delegates to specialist agents.",
        instruction=INSTRUCTION,
        sub_agents=[
            build_receipt_agent(),
            build_house_agent(),
            build_report_agent(sql_dialect),
            build_budget_agent(),
        ],
    )
