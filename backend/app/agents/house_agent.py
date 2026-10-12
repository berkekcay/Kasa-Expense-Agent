"""House agent (owner: track HOUSE): shared-flat expenses, splits, balances, settle-up,
recorded payments and reminders."""

from google.adk.agents import Agent

from app.agents.common import GUARDRAILS, chat_model, with_today
from app.agents.tools.house_tools import (
    add_house_expense_equal_split,
    get_house_balances,
    list_my_houses,
    record_payment,
)

INSTRUCTION = f"""\
You are Kasa's house agent. You manage expenses shared between flatmates.

- Always call `list_my_houses` first to find the house id and member user ids. If the user
  has one house, use it without asking.
- To record a shared bill split equally, call `add_house_expense_equal_split` right after
  `list_my_houses`, with the house id, what it was and the total as given. Leave paid_by
  empty when the user paid, and split_between empty when everyone shares it. Do not ask
  for confirmation. The tool computes every share; then report the shares it returned.
- For "who owes whom" or settling up, call `get_house_balances` and report its transfers
  exactly. Positive balance = the house owes that person.
- When someone says they paid a flatmate back, call `record_payment`.

{GUARDRAILS}"""


def build_house_agent() -> Agent:
    return Agent(
        name="house_agent",
        model=chat_model(),
        description=(
            "Shared flat/house money: adds a bill split between flatmates (ev, fatura bölüşme), "
            "shows balances and who owes whom, records paybacks between flatmates."
        ),
        instruction=with_today(INSTRUCTION),
        tools=[list_my_houses, add_house_expense_equal_split, get_house_balances, record_payment],
    )
