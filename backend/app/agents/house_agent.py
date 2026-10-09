"""House agent (owner: Agent dev #2): shared-flat expenses, equal splits, balances, settle-up."""

from google.adk.agents import Agent

from app.agents.common import GUARDRAILS, gemini_model
from app.agents.tools.house_tools import add_house_expense_equal_split, get_house_balances, list_my_houses

INSTRUCTION = f"""\
You are Kasa's house agent. You manage expenses shared between flatmates.

- Call `list_my_houses` first to find house ids and member user ids.
- To record a shared bill, call `add_house_expense_equal_split`; the tool computes shares.
- For "who owes whom" or settling up, call `get_house_balances` and report its transfers
  exactly. Positive balance = the house owes that person.

{GUARDRAILS}"""


def build_house_agent() -> Agent:
    return Agent(
        name="house_agent",
        model=gemini_model(),
        description="Shared flat expenses: equal splits, balances, who owes whom and settle-up.",
        instruction=INSTRUCTION,
        tools=[list_my_houses, add_house_expense_equal_split, get_house_balances],
    )
