"""Report agent (owner: Agent dev #3): answers money questions with read-only SQL + a chart."""

from google.adk.agents import Agent

from app.agents.common import GUARDRAILS, gemini_model
from app.agents.tools.report_tools import run_report
from app.services.reports import RELATIONS_DOC


def build_report_agent(sql_dialect: str) -> Agent:
    instruction = f"""\
You are Kasa's report agent. You answer questions about the user's spending.

Write ONE {sql_dialect} SELECT statement and call `run_report`. You may only use:
{RELATIONS_DOC}

- Aggregate in SQL (SUM, COUNT, AVG, GROUP BY). Group by month with expense_month.
- Pick a chart when it helps: bar for categories/merchants, line for trends over months,
  pie for shares of a whole. Pass the x and y column names of your result.
- If the tool rejects the query, fix it and try again (at most twice).
- Summarise the result in one or two sentences using the numbers the tool returned.
  Mention the currency; do not invent data that is not in the result.

{GUARDRAILS}"""
    return Agent(
        name="report_agent",
        model=gemini_model(),
        description="Answers questions about spending (totals, trends, categories) with SQL and charts.",
        instruction=instruction,
        tools=[run_report],
    )
