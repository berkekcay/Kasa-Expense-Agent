"""Receipt agent (owner: Agent dev #1): reads a receipt image or typed expense and saves it."""

from google.adk.agents import Agent

from app.agents.common import GUARDRAILS, gemini_model
from app.agents.tools.receipt_tools import list_recent_expenses, save_expense

INSTRUCTION = f"""\
You are Kasa's receipt agent. You turn receipt photos and typed purchases into saved expenses.

For a receipt image: read merchant, date, currency, grand total and line items, then call
`save_expense` exactly once. Copy numbers as printed (use '.' as decimal separator).
For a typed purchase ("spent 120 TL at Migros"), call `save_expense` with from_receipt=false.
If the image is not a receipt or the total is unreadable, do not save; say what is missing.
After saving, confirm merchant, date and total from the tool result and mention any warnings.

{GUARDRAILS}"""


def build_receipt_agent() -> Agent:
    return Agent(
        name="receipt_agent",
        model=gemini_model(),
        description="Reads receipt photos or typed purchases and saves them as expenses; lists recent expenses.",
        instruction=INSTRUCTION,
        tools=[save_expense, list_recent_expenses],
    )
