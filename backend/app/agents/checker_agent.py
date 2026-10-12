"""Checker agent (owner: track REPORT).

Reviews the report agent's draft answer against the rows `run_report` returned and flags
numbers, categories or dates that are not in the result (hallucinations). Planned wiring:
`build_report_agent` returns a SequentialAgent named "report_agent" that runs the SQL
agent and then this checker, so the coordinator's transfer target does not change.
The evals in backend/evals measure whether it helps.
"""

from google.adk.agents import Agent


def build_checker_agent() -> Agent:
    """Use chat_model(), GUARDRAILS and with_today from app.agents.common like the others."""
    raise NotImplementedError("build_checker_agent: track REPORT")
