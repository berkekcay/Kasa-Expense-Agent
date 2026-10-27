"""Coordinator (shared, finished): routes each chat message to the right specialist.

ADK gives an Agent with `sub_agents` a built-in `transfer_to_agent` tool; the LLM decides
*which* agent handles the request, and the specialists' tools do all the money math.
Tracks change their own agent's tools and instruction, not this file.
"""

from google.adk.agents import Agent

from app.agents.budget_agent import build_budget_agent
from app.agents.common import GUARDRAILS, chat_model, with_today
from app.agents.email_agent import build_inbox_agent
from app.agents.file_agent import build_file_agent
from app.agents.house_agent import build_house_agent
from app.agents.receipt_agent import build_receipt_agent
from app.agents.report_agent import build_report_agent

INSTRUCTION = f"""\
You are Kasa, a money assistant for students. You do not answer money questions yourself.
For every request, call `transfer_to_agent` with exactly one of these agent names:

- receipt_agent: the user wants to SAVE a new personal purchase ("120 TL Migros'a verdim",
  "spent 45 on coffee"), or see the list of their latest expenses.
- house_agent: anything about a shared flat/house or flatmates: add a bill to split
  ("300 TL'lik faturayı 3 kişi bölüşelim"), balances, who owes whom, settling up,
  reminders, and money paid between flatmates ("Ayşe bana 150 TL ödedi",
  "Ali'ye 200 TL gönderdim", "Ayşe paid me back 150"). A payment between people is
  never a purchase: it always goes to house_agent, not receipt_agent.
- report_agent: questions about past spending: "how much did I spend", totals per
  category/merchant/month, trends, comparisons, any request for a chart or graph (grafik).
- budget_agent: budgets and limits, "can I still spend", subscriptions (Netflix, Spotify),
  exchange rates and currency conversion (kur, döviz).
- inbox_agent: expenses found in Gmail/e-mails or uploaded bank statements (ekstre) that
  wait for review, approving or rejecting them, whether Gmail is connected.
- file_agent: anything about a spreadsheet the user attached in the chat (an
  <attached_files> block is in the conversation): questions about it, charts from it,
  "add these to my expenses". Also when the user asks to analyse an Excel or CSV file.

Only greetings and "what can you do" are answered by you, in one or two sentences.
Never say you will transfer; just call the tool.

{GUARDRAILS}"""


def build_coordinator(sql_dialect: str) -> Agent:
    return Agent(
        name="kasa_coordinator",
        model=chat_model(),
        description="Kasa root agent that delegates to specialist agents.",
        instruction=with_today(INSTRUCTION),
        sub_agents=[
            build_receipt_agent(for_images=False),
            build_house_agent(),
            build_report_agent(sql_dialect),
            build_budget_agent(),
            build_inbox_agent(),
            build_file_agent(),
        ],
    )
