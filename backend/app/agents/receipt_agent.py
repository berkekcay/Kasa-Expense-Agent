"""Receipt agent (owner: shared, Sprint 1): reads a receipt image or typed expense and saves it."""

from google.adk.agents import Agent

from app.agents.common import GUARDRAILS, chat_model, vision_model, with_today
from app.agents.tools.receipt_tools import list_recent_expenses, save_expense
from app.services.categories import CATEGORIES

INSTRUCTION = f"""\
You are Kasa's receipt agent. You turn receipt photos and typed purchases into saved expenses.

For a receipt image: read merchant, date, currency, grand total and line items, then call
`save_expense` exactly once. Copy numbers as printed (use '.' as decimal separator).
For a typed purchase ("spent 120 TL at Migros"), call `save_expense` with from_receipt=false.
Pick category from: {", ".join(CATEGORIES)}.
If the image is not a receipt or the total is unreadable, do not save; say what is missing.
After saving, confirm merchant, date and total from the tool result and mention any warnings.
To show what was saved recently, call `list_recent_expenses`.

{GUARDRAILS}"""


def build_receipt_agent(for_images: bool = True) -> Agent:
    """`for_images=True` (the /receipts runner) uses the vision model; inside the chat
    coordinator it handles typed purchases, so it uses the chat model."""
    return Agent(
        name="receipt_agent",
        model=vision_model() if for_images else chat_model(),
        description=(
            "Saves a new personal purchase/expense (receipt photo or typed, e.g. 'spent 120 TL at "
            "Migros') and lists the user's recent expenses."
        ),
        instruction=with_today(INSTRUCTION),
        tools=[save_expense, list_recent_expenses],
    )
