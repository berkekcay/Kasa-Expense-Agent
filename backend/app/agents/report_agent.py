"""Report agent (owner: track REPORT): answers money questions with read-only SQL + a chart."""

from google.adk.agents import Agent

from app.agents.common import GUARDRAILS, chat_model, with_today
from app.agents.tools.report_tools import run_report
from app.services.reports import RELATIONS_DOC


def build_report_agent(sql_dialect: str) -> Agent:
    month_hint = "strftime('%Y-%m', 'now')" if sql_dialect == "sqlite" else "CONVERT(CHAR(7), GETDATE(), 126)"
    instruction = f"""\
You are Kasa's report agent. You answer questions about the user's spending.

Write ONE {sql_dialect} SELECT statement and call `run_report`. You may only use:
{RELATIONS_DOC}

- Aggregate in SQL (SUM, COUNT, AVG, GROUP BY). Group by month with expense_month.
  "This month" means expense_month = {month_hint} (or the YYYY-MM of today's date below).
- Pick a chart when it helps: bar for categories/merchants, line for trends over months,
  pie for shares of a whole. Pass the x and y column names of your result.
- If the tool rejects the query, fix it and try again (at most twice).
- Summarise the result in one or two sentences using the numbers the tool returned.
  Mention the currency; do not invent data that is not in the result.

{GUARDRAILS}"""
    return Agent(
        name="report_agent",
        model=chat_model(),
        description=(
            "Answers questions about past spending: totals, per category or merchant, trends over "
            "months, 'how much did I spend', and draws charts (grafik)."
        ),
        instruction=with_today(instruction),
        tools=[run_report],
    )
