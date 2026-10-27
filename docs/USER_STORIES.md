# Kasa user stories

This file lists what Kasa does for its users, who owns each part, and how far each part is.
Every status was checked against the code and the tests on `main` on 2026-10-27. Each story
names the endpoint, page or test file that proves it, so anyone can check it again.

Status:

- **Done**: the code is on `main`, automated tests cover it, and it works without any outside
  service.
- **Partial**: the code exists, but one part has never run against the real service (Gemini,
  Google, Azure SQL, Firebase, Cloud Run), or there is a known gap. The note says which.
- **Not started**: there is no code for it yet.

Partial and Not started stories become GitHub issues. The list is at the end.

## Sprints

The README has a Sprint 1 checklist, a Sprint 2 foundation list and four tracks for sprints 2
to 4 (HOUSE, MONEY, INGEST, REPORT). It does not say which track belongs to which sprint, so
this file uses the following plan. The team can move stories between sprints.

| Sprint | Scope |
| --- | --- |
| 1 | The README "Sprint 1 checklist": receipt photo, manual expenses, one house with equal splits, balances, settle-up, chat with a chart |
| 2 | The "Sprint 2 foundation" (migrations, data model, recorded payments, categories, Firebase option, Ollama switch, CI) and the HOUSE track |
| 3 | The MONEY and INGEST tracks |
| 4 | The REPORT track (checker agent, evals), the deployment kit, the API gap fixes, and everything still open |

## Roles

Owner roles come from the project page. The names of the people are in [TEAM.md](TEAM.md).

| Short name | Role | Main areas |
| --- | --- | --- |
| Product owner | Product owner and architecture | user stories, architecture, demo, priorities |
| Backend | Database and backend | data model, migrations, RLS, REST API, Google OAuth and Gmail plumbing |
| Agents 1 | Agent developer #1 | coordinator, receipt agent, budget agent (MONEY track), inbox and statement parsing agents |
| Agents 2 | Agent developer #2 | house agent, splits, balances, settle-up, Calendar reminders (HOUSE track) |
| Agents 3 / QA | Agent developer #3, QA and cloud | report agent, checker agent, evals, CI, Cloud Run and Azure SQL deploy |
| Frontend | Frontend | Next.js pages and components |

The project page does not name an owner for the inbox and statement agents. This file gives
them to Agents 1 because they parse purchases like the receipt agent does.

## Personas

**Elif, a student living alone.** First year, lives in a studio in Kadıköy on a KYK
scholarship and some family money. Pays for groceries, transport, coffee and two or three
subscriptions. She wants to see where the money goes each month and to get a warning before a
category runs out. She writes in Turkish and sometimes in English.

**Ali, a student in a shared flat.** Shares a flat in Moda with two friends. Rent, bills and
house shopping are paid by whoever is at the shop or has money that week. He does not want to
keep a spreadsheet. He wants to know what he owes and to whom, and to pay it in as few
transfers as possible.

**Deniz, the flat's "accountant".** Lives with Ali and Ayşe and pays the rent every month,
then collects the shares. Deniz enters the bills, picks how each one is split (equal, by
room size, by item), records the money that comes back and reminds people to settle up. Deniz
also imports the bank statement once a month so no purchase is forgotten. The demo user in
[DEMO.md](DEMO.md) is Deniz.

## Epic: capture expenses

### US-CAPTURE-01 Add an expense by hand

As Elif, I want to add an expense by hand so that purchases without a receipt are counted.

- Sprint 1 · **Done** · Owner: Backend (API), Frontend (form)
- Given I am on the Expenses page, when I enter "Migros", "84,90" and save, then the expense
  appears at the top of the list with a category Kasa picked ("groceries").
- Given I enter a category in Turkish ("market") or leave it empty, when I save, then it is
  stored as one of the 12 fixed categories.
- Given I enter 0, a negative amount or more than two decimals, when I save, then I get a clear
  error and nothing is saved.
- Evidence: `POST /expenses`, `GET /categories`, page `/expenses`,
  `tests/test_api.py::test_create_and_list_expenses_is_scoped_per_user`,
  `tests/test_api.py::test_expense_validation`,
  `tests/test_foundation_api.py::test_categories_endpoint_and_normalised_storage`.

### US-CAPTURE-02 Save a receipt from a photo

As Elif, I want to take a photo of a receipt so that the merchant, date, lines and total are
saved without typing.

- Sprint 1 · **Partial** · Owner: Agents 1 (receipt agent), Frontend (upload page)
- Given the server has an LLM provider, when I upload `receipt_market.png`, then an expense
  "ÖZDEMİR MARKET" of 239.35 TRY dated 2026-10-05 is saved with its five lines.
- Given the lines do not add up to the total, when it is saved, then I see a warning.
- Given no LLM provider is configured, when I open the page, then it says receipt reading is
  off and the API answers 503.
- Evidence: `POST /receipts`, page `/receipts`,
  `tests/test_agents_offline.py::test_receipt_upload_saves_expense_via_agent` (scripted fake
  model), `tests/test_live.py::test_live_receipt_image` (live only).
- Gap: passed live on Ollama (`qwen3-vl:8b`). Never run on Gemini, so receipt vision with
  `gemini-3.5-flash-lite` is not verified.

### US-CAPTURE-03 Tell the chat about a purchase

As Elif, I want to write "Bugün Migros'ta 245,90 TL harcadım" so that the expense is saved
from one sentence.

- Sprint 1 · **Partial** · Owner: Agents 1
- Given I send that message, when the coordinator routes it, then the receipt agent calls
  `save_expense` and the answer confirms the amount in Turkish.
- Given I ask "son harcamalarım neler?", then the receipt agent lists my latest expenses.
- Evidence: `POST /chat`, page `/chat`, `app/agents/tools/receipt_tools.py`, eval case
  `route-receipt-tr` in `backend/evals/cases.jsonl` (passed on Ollama, `evals/latest.md`).
- Gap: not verified on Gemini.

### US-CAPTURE-04 Pay in another currency

As Elif, I want to enter a purchase in USD or EUR so that it is converted to TL with the
official TCMB rate of that day.

- Sprint 3 · **Done** · Owner: Agents 1 (MONEY track), Backend
- Given I add 15.00 USD, when I save, then the total is stored in TRY with the original
  amount, the rate and the bulletin date, and I see "Converted 15.00 USD to ... TRY at TCMB
  rate ... (date)".
- Given the day is a weekend or a holiday, when I save, then the latest earlier bulletin is
  used. Given TCMB cannot be reached, then a cached rate from the last 7 days is used, or the
  save is refused with a clear message.
- Given a house uses EUR, when a bill is added in TRY, then it is converted to EUR before it
  is split.
- Evidence: `POST /expenses`, `GET /fx/rates`, `GET /fx/convert`, page `/expenses`,
  `tests/test_foundation_api.py::test_foreign_currency_expense_is_converted_with_a_warning`,
  `tests/test_money_fx.py::test_foreign_expense_through_the_api_and_a_house_in_euros`,
  `tests/test_money_fx.py::test_holiday_walks_back_and_remembers_the_missing_day`.

### US-CAPTURE-05 Fix or delete an expense

As Elif, I want to change the merchant, category, date or note of an expense, or delete it, so
that mistakes do not stay in my numbers.

- Sprint 4 · **Done** · Owner: Backend, Frontend
- Given my own expense, when I edit the category, then only that field changes. Amounts cannot
  be edited; I delete and add again.
- Given a house bill, when I try to delete it from my expense list, then I get 409 and a
  pointer to the house endpoint, so balances stay right.
- Given someone else's expense id, when I edit or delete it, then I get 404.
- Evidence: `PATCH /expenses/{id}`, `DELETE /expenses/{id}`, page `/expenses`,
  `tests/test_expenses_api.py` (`test_patch_changes_only_the_given_fields`,
  `test_house_expense_is_409_and_points_to_the_house_endpoint`, `test_others_get_404`).

### US-CAPTURE-06 Filter my expenses

As Elif, I want to filter by month, category, source and personal or house so that I can find
one purchase quickly.

- Sprint 4 · **Done** · Owner: Backend, Frontend
- Given 150 expenses, when I filter by "2026-10" and "food", then only those come back, newest
  first, and the total count is in the `X-Total-Count` header for paging.
- Evidence: `GET /expenses?month=&category=&source=&scope=&limit=&offset=`, page `/expenses`,
  `tests/test_expenses_api.py::test_month_category_source_and_scope`,
  `tests/test_expenses_api.py::test_paging_keeps_the_total`.

## Epic: personal budgets

### US-BUDGET-01 Set a monthly budget

As Elif, I want a monthly limit per category, or overall, so that I know how much is left.

- Sprint 3 · **Done** · Owner: Agents 1 (MONEY track), Frontend
- Given I set groceries to 3000 TL, when I set it again to 3500 TL, then the same budget is
  updated (one per category).
- Given I write "Ulaşım için aylık 1500 TL bütçe koy" in the chat, then the budget agent sets
  it for me.
- Evidence: `GET /budgets`, `PUT /budgets`, `DELETE /budgets/{id}`, `GET /budgets/status`,
  page `/budgets`, `tests/test_money_budgets.py::test_set_budget_upserts_and_normalises`,
  `tests/test_money_budgets.py::test_budget_api`,
  `tests/test_money_tools.py::test_set_budget_and_status_tools`.

### US-BUDGET-02 Warn me when a budget is close or exceeded

As Elif, I want a warning when an expense takes a budget past 80% or over the limit so that I
can slow down in time.

- Sprint 3 · **Done** · Owner: Agents 1, Backend
- Given entertainment is at 84% of 1200 TL, when I add a 15 USD purchase in entertainment,
  then the response says the entertainment budget is exceeded, with the amounts.
- Given a budget is already at "warning", when I add a small expense that keeps it there,
  then I am not warned again.
- Given I pay a house bill for three people, then only my share counts toward my budget.
- Evidence: `POST /expenses` (warnings), dashboard budget meters,
  `tests/test_money_budgets.py::test_alerts_only_when_crossing_a_level`,
  `tests/test_money_budgets.py::test_status_counts_personal_and_own_house_shares_only`,
  `tests/test_integration.py::test_house_bill_warns_on_payers_share_only`.

### US-BUDGET-03 See my month at a glance

As Elif, I want one page with this month's total, the categories, a six month trend, budgets,
house balances and upcoming charges so that I do not have to ask.

- Sprint 3 · **Done** · Owner: Agents 1 (MONEY track), Frontend
- Given I have expenses, when I open the dashboard, then I see the total, the change from last
  month, bars per category and a line for six months.
- Given items wait in the inbox, then a banner links to the inbox.
- Evidence: `GET /dashboard`, page `/`, `tests/test_money_dashboard.py`.

### US-BUDGET-04 Find my subscriptions

As Elif, I want Kasa to find my monthly charges (Netflix, Spotify) so that I see what I pay
every month and what is due soon.

- Sprint 3 · **Done** · Owner: Agents 1 (MONEY track), Frontend
- Given three monthly Netflix charges of 229.99 TL, when detection runs, then a monthly
  "Netflix" subscription appears with the next expected date.
- Given I buy groceries every month, then that is not a subscription.
- Given I dismiss a subscription, then it never comes back.
- Evidence: `GET /subscriptions`, `POST /subscriptions/detect`, `GET /subscriptions/upcoming`,
  `POST /subscriptions/{id}/dismiss`, page `/subscriptions`, `tests/test_money_subscriptions.py`,
  `tests/test_integration.py::test_monthly_groceries_are_not_subscriptions`.

### US-BUDGET-05 Ask about budgets, subscriptions and rates in chat

As Elif, I want to ask "Am I over any budget?", "Spotify aboneliğim ne kadar tutuyor?" or "100
dolar kaç TL?" so that I get the answer without opening pages.

- Sprint 3 · **Partial** · Owner: Agents 1
- Given I ask one of these, then the coordinator sends it to the budget agent and the answer
  quotes amounts from its tools.
- Evidence: `POST /chat`, `app/agents/budget_agent.py`, `app/agents/tools/budget_tools.py`,
  `tests/test_money_tools.py::test_chat_routes_to_budget_agent_and_saves_for_the_caller`,
  eval cases `route-budget-set-tr` and `route-subscriptions-en`.
- Gap: on Ollama, `route-subscriptions-en` answered an English question in Turkish
  (`evals/latest.md`). Not verified on Gemini.

## Epic: shared houses

### US-HOUSE-01 Create a house and add flatmates

As Deniz, I want to create "Moda evi" and add Ali and Ayşe so that we can share bills.

- Sprint 1 · **Done** · Owner: Agents 2 (HOUSE track), Backend, Frontend
- Given I create a house, then I am its first member. Given I add "ayse", then she is a
  member and sees the house when she signs in.
- Given someone who is not a member asks for the house, then they get 404 (house ids cannot be
  probed).
- Evidence: `POST /houses`, `GET /houses`, `POST /houses/{id}/members`, page `/houses`
  (Members tab), `tests/test_api.py::test_house_access_is_members_only`.

### US-HOUSE-02 Invite a flatmate with a link

As Deniz, I want to send an invite link that Ali accepts so that nobody is added to a house
without saying yes.

- Sprint 4 · **Not started** · Owner: Backend, Frontend
- Given I create an invite, when Ali opens the link while signed in, then he joins the house.
- Given nobody accepts, then nobody is added.
- Today any member can add any user id (`app/services/houses.py`, `add_member`: "Later: invite
  links + Firebase accounts").

### US-HOUSE-03 Split a bill equally

As Deniz, I want to split the internet bill equally so that everyone pays the same.

- Sprint 1 · **Done** · Owner: Agents 2
- Given a 100.00 TL bill for three people, when it is saved, then the shares are 33.34,
  33.33 and 33.33 and always add up to the total.
- Given I choose only two of the three people, then only they share it.
- Evidence: `POST /houses/{id}/expenses`, page `/houses` (Add expense, Equal),
  `tests/test_settlement.py`, `tests/test_api.py::test_house_equal_split_balances_and_settle_up`.

### US-HOUSE-04 Split by percent, exact amounts or per item

As Deniz, I want to split electricity 40/30/30 by room size, groceries by exact amounts, or a
Migros receipt by who had which line so that splits are fair.

- Sprint 2 · **Done** · Owner: Agents 2, Frontend
- Given percents that add up to 100, when I save, then each share is that percent of the total
  and the shares add up exactly. Given percents that add up to 90, then I get an error.
- Given exact amounts that do not add up to the total, then the error says how much is
  missing or too much.
- Given per item lines with people ticked, then each line is shared by its people, and tax or
  a discount is spread in proportion.
- Evidence: `POST /houses/{id}/expenses/split`, page `/houses` (Add expense),
  `tests/test_house_api.py` (`test_percent_split`, `test_exact_split_and_paid_by`,
  `test_items_split_stores_assignees_and_lists_them`), `tests/test_house_splits.py`.

### US-HOUSE-05 See who owes whom

As Ali, I want to see my balance and the transfers that settle the house so that I know whom
to pay and how much.

- Sprint 1 · **Done** · Owner: Agents 2, Frontend
- Given the bills and payments of the house, when I open Balances, then every member's net
  balance is shown and the balances add up to zero.
- Given any group of n people, then settle-up suggests at most n - 1 transfers.
- Evidence: `GET /houses/{id}/balances`, page `/houses` (Balances), dashboard "House
  balances", `tests/test_settlement.py::test_random_groups_settle_exactly_with_at_most_n_minus_1_transfers`.

### US-HOUSE-06 Record a payment between flatmates

As Deniz, I want to record "Ali paid me 6000 TL" so that the balances go down.

- Sprint 2 · **Done** · Owner: Agents 2, Frontend
- Given Ali owes me 6128.33 TL, when I record 6000 TL from Ali to me, then he owes 128.33 TL.
- Given I type 60000 by mistake, then the payment is refused and the message names the largest
  amount that fits, unless I tick "advance or loan".
- Given I recorded a payment, then only I can undo it.
- Evidence: `POST /houses/{id}/settlements`, `GET /houses/{id}/settlements`,
  `DELETE /houses/{id}/settlements/{id}`, page `/houses` (Balances, Payments),
  `tests/test_house_api.py::test_overpayment_is_refused_unless_allowed`,
  `tests/test_house_api.py::test_delete_payment_by_creator_only`,
  `tests/test_foundation_api.py::test_recorded_payments_reduce_balances`.

### US-HOUSE-07 Remind everyone to settle up

As Deniz, I want reminders with a due date, also in Google Calendar, so that I do not have to
chase people.

- Sprint 3 · **Partial** · Owner: Agents 2
- Given open transfers, when I create reminders for a date, then one reminder per transfer is
  saved. Given a connected Google account, then each becomes an all day Calendar event with
  both flatmates invited.
- Given the balances change, when I create reminders again, then old ones are cancelled as
  "outdated".
- Evidence: `POST /houses/{id}/reminders`, `GET /houses/{id}/reminders`,
  `PATCH /houses/{id}/reminders/{id}`, page `/houses` (Reminders),
  `tests/test_house_reminders.py`.
- Gap: Calendar calls are tested with fakes only. They have never run against Google, because
  no OAuth client is set up.

### US-HOUSE-08 Leave a house, remove a member, delete a bill

As Ali, I want to leave the house when I move out, and as the payer, delete a wrong bill, so
that the house stays correct.

- Sprint 4 · **Done** · Owner: Agents 2, Frontend
- Given my balance is zero, when I leave, then I am removed and past bills stay. Given it is
  not zero, then I get 409 with the amount to settle first. The last member cannot leave.
- Given I paid a bill, when I delete it, then its shares go and balances follow. Others get 403.
- Evidence: `DELETE /houses/{id}/members/{user_id}`, `DELETE /houses/{id}/expenses/{id}`,
  page `/houses` (Members, Expenses), `tests/test_house_members.py`.

### US-HOUSE-09 Run the house from the chat

As Deniz, I want to write "Evdeki 300 TL'lik su faturasını ben ödedim, 3 kişi arasında eşit
bölüştür" or "Ayşe bana 150 TL ödedi" so that I do not fill in forms.

- Sprint 2 · **Partial** · Owner: Agents 2
- Given that message, then the house agent finds my house, splits the bill or records the
  payment with tools and confirms in Turkish. Names like "Ayşe" are matched to members.
- Evidence: `POST /chat`, `app/agents/house_agent.py`, `app/agents/tools/house_tools.py`,
  `tests/test_house_tools.py`, `tests/test_live.py::test_live_chat_house_equal_split` (live
  only), eval cases `route-house-split-tr` and `route-house-balance-tr`.
- Gap: passed on Ollama, not verified on Gemini.

## Epic: ask in plain language

### US-ASK-01 Ask about my spending and get a chart

As Elif, I want to ask "Bu ay kategoriye göre ne kadar harcadım? Grafik çiz" so that I get the
numbers and a chart.

- Sprint 1 · **Partial** · Owner: Agents 3 / QA (report agent), Frontend (chart)
- Given my expenses, when I ask that, then the report agent writes one SELECT, the guard and
  the checker pass it, and the answer comes back with a bar chart that the chat page draws.
- Given I ask for a trend, then I get a line chart. Given a plain list, then a table.
- Evidence: `POST /chat` (`chart` in the response), page `/chat`,
  `tests/test_agents_offline.py::test_chat_routes_to_report_agent_and_returns_chart`,
  `tests/test_reports.py`, `tests/test_report_guard.py`, eval cases `report-*` (6 of 6 passed
  on Ollama).
- Gap: not verified on Gemini.

### US-ASK-02 Totals count only my share of house bills

As Deniz, I want "how much did I spend" to count my share of the rent, not the whole rent I
paid, so that the chat, the dashboard and the budgets give the same number.

- Sprint 4 · **Done** · Owner: Agents 3 / QA
- Given I paid 18000 TL rent for three people, when I ask how much I spent this month, then
  6000 TL of it counts.
- Given the model sums whole house bills, then the guard sends the query back for a rewrite.
- Evidence: relation `my_spending` in `app/services/reports.py`,
  `tests/test_integration.py::test_my_spending_matches_dashboard_and_blocks_double_counting`,
  `tests/test_report_guard.py` (`test_house_shares_use_my_share_not_the_bill`).

### US-ASK-03 A second agent checks every query

As the product owner, I want a checker agent to compare each query with the question so that
wrong months or wrong filters are fixed before the answer is shown.

- Sprint 4 · **Done** · Owner: Agents 3 / QA
- Given a query that does not match the question, then the checker answers "revise" with a
  reason, and the report agent fixes it (at most twice).
- Given the checker fails or times out, then the query runs on the static guard alone and the
  result says so.
- Evidence: `app/agents/checker_agent.py`, `app/agents/tools/report_tools.py`,
  `tests/test_report_checker.py`.

### US-ASK-04 The chat answers in my language

As Elif, I want an English question to get an English answer and a Turkish one a Turkish
answer.

- Sprint 4 · **Partial** · Owner: Agents 1 (coordinator), Agents 3 / QA (evals)
- Given "How much did I spend on groceries last month?", then the answer is in English.
- Evidence: `app/agents/language.py`, `tests/test_integration.py::test_reply_language_detection`,
  the `lang` check in `evals/run_evals.py`.
- Gap: one of six routing cases failed the language check on Ollama. Not measured on Gemini.

### US-ASK-05 The right specialist answers

As any user, I want each message to reach the agent that can handle it (receipt, house,
report, budget, inbox) so that I can ask anything in one chat.

- Sprint 1 · **Partial** · Owner: Agents 1 (coordinator), Agents 3 / QA (evals)
- Given a payment between flatmates ("Ali'ye 200 TL gönderdim"), then it goes to the house
  agent, never to the receipt agent.
- Evidence: `app/agents/coordinator.py`, `tests/test_agents_offline.py::test_every_runner_kind_builds`,
  eval cases `route-*` (5 of 6 passed on Ollama; the failure was the reply language).
- Gap: not verified on Gemini.

### US-ASK-06 Kasa runs on Gemini

As the product owner, I want the agents to run on Gemini with a free AI Studio key so that the
product works without the team's Ollama server.

- Sprint 4 · **Partial** · Owner: Agents 3 / QA
- Given `LLM_PROVIDER=gemini`, a key and `GEMINI_MODEL=gemini-3.5-flash-lite`, when I run
  `KASA_LIVE_TESTS=1 pytest -m live -s` and `python -m evals.run_evals`, then the live tests
  pass and the evals score at least as well as on Ollama.
- Evidence: `app/agents/common.py` (`build_model`), `app/config.py`.
- Gap: the default model is now `gemini-3.5-flash-lite`, because new keys cannot use the 2.5
  models. No live Gemini call has been made yet, receipt vision included. A separate issue
  covers it.

## Epic: inbox and imports

### US-INBOX-01 Import a CSV bank statement

As Deniz, I want to upload my bank's CSV export so that every card purchase becomes an item
to review.

- Sprint 3 · **Done** · Owner: Agents 1 (INGEST), Backend, Frontend
- Given a Garanti style export (semicolons, Windows-1254, "1.234,56"), when I upload it, then
  every spending line becomes a pending inbox item, and income, card payments and refunds are
  skipped.
- Given I upload the same file again, then nothing new is created ("Duplicates").
- Evidence: `POST /imports/statement`, page `/import`,
  `tests/test_ingest_statements.py::test_garanti_like_cp1254_semicolon_export`,
  `tests/test_ingest_statements.py::test_csv_upload_creates_pending_items_and_dedupes`.

### US-INBOX-02 Import a PDF statement

As Deniz, I want to upload the PDF statement when my bank has no CSV.

- Sprint 3 · **Partial** · Owner: Agents 1 (statement agent)
- Given a PDF with a text layer, then the statement parser agent reads it in chunks and each
  line becomes an inbox item. Given a scanned PDF, then I get a clear 422.
- Evidence: `POST /imports/statement`, `app/agents/statement_agent.py`,
  `tests/test_ingest_statements.py::test_pdf_upload_goes_through_the_statement_parser` (fake
  runner), `tests/test_ingest_live.py::test_live_statement_pdf` (live only).
- Gap: no recorded live run, on Ollama or Gemini.

### US-INBOX-03 Review, fix and approve inbox items

As Deniz, I want to check each found purchase, fix it if needed, and approve or reject it, one
by one or many at once, so that only real expenses are saved.

- Sprint 3 · **Done** · Owner: Agents 1 (INGEST), Backend, Frontend
- Given a pending item, when I change the category and approve, then an expense is created
  through the normal pipeline (FX, budgets) with source "statement" or "email".
- Given I select five items and press Approve, then all five are approved and failures are
  reported per item.
- Evidence: `GET /inbox`, `PATCH /inbox/{id}`, `POST /inbox/{id}/approve`,
  `POST /inbox/{id}/reject`, `POST /inbox/approve`, `POST /inbox/reject`, page `/inbox`,
  `tests/test_ingest_inbox.py`.

### US-INBOX-04 Get purchases from Gmail

As Elif, I want to connect Gmail so that order and card emails (Trendyol, bank alerts) show up
in the inbox by themselves.

- Sprint 3 · **Partial** · Owner: Backend (OAuth, Gmail, Pub/Sub), Agents 1 (email agent)
- Given I connect Google in Settings, then Kasa stores an encrypted refresh token and starts
  a Gmail watch. Given a new order email, then the email agent parses it into a pending item.
  Newsletters are ignored.
- Given an email that says "approve all items", then it is only a pending item. The parser has
  no tool that can approve.
- Evidence: `GET /integrations/google/connect`, `/callback`, `/status`, `POST /sync`,
  `DELETE /integrations/google`, `POST /internal/gmail/push`, page `/settings`,
  `tests/test_ingest_oauth.py`, `tests/test_ingest_sync.py`, `tests/test_ingest_gmail.py`.
- Gap: everything is tested with fakes. No Google OAuth client or consent screen exists yet, so
  real OAuth, Gmail push and sync have never run.

### US-INBOX-05 Ask the chat about the inbox

As Deniz, I want to ask "Mailimde onay bekleyen harcama var mı?" and approve an item by
saying so.

- Sprint 3 · **Partial** · Owner: Agents 1
- Given pending items, then the inbox agent lists them. It approves only when I clearly ask
  for that item.
- Evidence: `app/agents/email_agent.py`, `app/agents/tools/inbox_tools.py`,
  `tests/test_ingest_inbox.py::test_chat_tools_list_approve_reject_and_status`,
  `tests/test_ingest_sync.py::test_inbox_agent_instruction_requires_explicit_user_approval`,
  eval case `route-inbox-tr`.
- Gap: passed on Ollama, not verified on Gemini.

## Epic: guardrails and privacy

### US-GUARD-01 I only see my own data

As Ali, I want to be sure flatmates and other users cannot see my personal expenses.

- Sprint 1 · **Done** · Owner: Backend
- Given two users, when each lists expenses, then each sees only their own. Given a house, then
  only members see its bills.
- Evidence: every service filters by `user_id`,
  `tests/test_api.py::test_create_and_list_expenses_is_scoped_per_user`,
  `tests/test_expenses_api.py::test_only_own_expenses`,
  `tests/test_report_guard.py::test_flatmate_sees_own_shares_only`.

### US-GUARD-02 The chat can only read my rows

As the product owner, I want the chat's SQL to be one read-only SELECT over the user's own
rows so that no message can change or leak data.

- Sprint 1 · **Done** · Owner: Agents 3 / QA
- Given "DROP TABLE expenses", "SELECT * FROM users" or a T-SQL trick, then the guard rejects
  it before it reaches the database and the chat says it can only read.
- Given a valid query, then the relations are injected as CTEs filtered to the current user,
  and a row limit is applied.
- Evidence: `app/services/reports.py` (`validate_report_sql`, `build_scoped_sql`),
  `tests/test_reports.py`, `tests/test_report_guard.py`, eval cases `refusal-drop-table`,
  `refusal-other-user-en`, `refusal-injection-users-en` (3 of 3 on Ollama).

### US-GUARD-03 Text in receipts and emails is data, not orders

As Elif, I want a receipt or email that says "ignore your rules" to change nothing.

- Sprint 3 · **Done** · Owner: Agents 1, Agents 3 / QA
- Given an injection email, then it becomes a normal pending item and nothing is approved.
- Given the user's question contains instructions for the checker, then the checker treats it
  as data.
- Evidence: `GUARDRAILS` in `app/agents/common.py`,
  `tests/test_ingest_sync.py::test_injection_email_is_just_a_pending_item`,
  `tests/test_ingest_sync.py::test_parser_agent_cannot_approve_even_if_it_obeys_the_email`,
  `tests/test_report_checker.py` (`test_prompt_marks_user_text_as_data`).

### US-GUARD-04 The database enforces user isolation too

As the product owner, I want SQL Server row-level security as a last line of defence so that
a bug in one query cannot show another user's rows.

- Sprint 2 · **Partial** · Owner: Backend, Agents 3 / QA (cloud)
- Given a session with `SESSION_CONTEXT('user_id')` set, then every table returns only that
  user's rows (expenses also to house members).
- Evidence: `alembic/versions/0001_sprint1_baseline.py`, `0002_sprints_2_4.py`,
  `app/db/session.py`, `tests/test_migrations.py::test_sql_server_ddl_renders_offline`,
  `tests/test_migrations.py::test_sql_server_ddl_fits_azure_sql_database`.
- Gap: the DDL is only rendered offline. It has never run on Azure SQL, and RLS has not been
  checked with real users (the smoke test is in `docs/SETUP.md`).

### US-GUARD-05 Money is always exact

As Ali, I want every share and conversion to add up to the kuruş so that nobody loses money to
rounding.

- Sprint 1 · **Done** · Owner: Backend, Agents 2
- Given any split, then the shares add up to the total. Given a conversion, then it is rounded
  once, half to even.
- Evidence: `app/services/money.py`, `app/services/splits.py`, `app/services/fx.py`,
  property tests in `tests/test_house_splits.py` and `tests/test_settlement.py`,
  `tests/test_money_fx.py::test_convert_minor_rounds_half_even`.

### US-GUARD-06 No secrets in code or logs

As the product owner, I want keys only in environment variables and Google tokens encrypted so
that a leaked repository or log reveals nothing.

- Sprint 2 · **Done** · Owner: Backend
- Given a Google refresh token, then it is stored Fernet-encrypted and never logged.
- Evidence: `app/config.py`, `app/services/crypto.py`, `.gitignore` (`.env`),
  `tests/test_ingest_oauth.py::test_tokens_never_reach_the_logs`,
  `tests/test_categories_crypto.py`.

### US-GUARD-07 Limit chat use per user

As the product owner, I want a per-user limit on `/chat` and `/receipts` so that one user (or a
loop) cannot use up the free Gemini quota for everyone.

- Sprint 4 · **Not started** · Owner: Backend
- Given a user sends more than N messages a minute, then they get 429 with a clear message.
- There is no rate limiting in `backend/app` today.

### US-GUARD-08 Delete my account and data

As Elif, I want to delete my account and everything Kasa stored about me so that I stay in
control of my data (KVKK).

- Sprint 4 · **Not started** · Owner: Backend, Frontend
- Given I confirm, then my expenses, budgets, subscriptions, inbox items and Google connection
  are deleted, and house bills with others are handled without breaking their balances.
- Today only the Google connection can be removed (`DELETE /integrations/google`).

## Epic: accounts

### US-ACCOUNT-01 Sign in with Google

As Elif, I want to sign in with my Google account so that my data is mine on every device.

- Sprint 2 · **Partial** · Owner: Backend, Frontend
- Given `FIREBASE_PROJECT_ID` is set, then every request needs a Firebase ID token, and my
  name and email are saved from it.
- Evidence: `app/auth.py`, `frontend/src/lib/auth.ts`, the "Sign in with Google" button in the
  nav bar, `tests/test_foundation_api.py` (`test_requires_bearer_token`,
  `test_valid_token_sets_user_and_profile`, with a faked verifier).
- Gap: no Firebase project is configured, so real sign-in has never run.

### US-ACCOUNT-02 Act as any user in dev mode

As a developer or presenter, I want to switch users by typing an id so that I can show two
flatmates without two Google accounts.

- Sprint 1 · **Done** · Owner: Backend, Frontend
- Given no Firebase settings, when I type "demo" in the Dev user box and press Switch, then
  every request carries `X-User-Id: demo`.
- Evidence: `app/auth.py`, `frontend/src/components/Nav.tsx` (`DevUserSwitcher`),
  `tests/test_api.py::test_default_dev_user_without_header`.

### US-ACCOUNT-03 Change my display name

As Ali, I want to set the name my flatmates see.

- Sprint 4 · **Done** · Owner: Backend, Frontend
- Given I change my name in Settings, then the house shows the new name.
- Evidence: `GET /me`, `PATCH /me`, page `/settings`,
  `tests/test_expenses_api.py::test_get_and_patch_display_name`,
  `tests/test_expenses_api.py::test_house_members_show_the_new_name`.

### US-ACCOUNT-04 Open Kasa at a public address

As Elif, I want to open Kasa on my phone at a public URL so that I can use it outside the lab.

- Sprint 4 · **Partial** · Owner: Agents 3 / QA (cloud)
- Given the deploy scripts run, then `kasa-api` and `kasa-web` run on Cloud Run with Azure SQL
  and Firebase, and the smoke test in `docs/SETUP.md` passes.
- Evidence: `deploy/*.sh`, `.github/workflows/deploy.yml`, `docs/SETUP.md`.
- Gap: the scripts were checked with `bash -n` and a stubbed `gcloud` only. Nothing is deployed.

## Traceability

One row per story. "Live only" tests run with `KASA_LIVE_TESTS=1`. All test paths are under
`backend/tests/`.

| Story | Status | API endpoint(s) | Frontend page | Tests |
| --- | --- | --- | --- | --- |
| US-CAPTURE-01 | Done | `POST /expenses`, `GET /categories` | `/expenses` | `test_api.py`, `test_foundation_api.py` |
| US-CAPTURE-02 | Partial | `POST /receipts` | `/receipts` | `test_agents_offline.py`, `test_live.py` (live only) |
| US-CAPTURE-03 | Partial | `POST /chat` | `/chat` | eval `route-receipt-tr` |
| US-CAPTURE-04 | Done | `POST /expenses`, `GET /fx/*` | `/expenses` | `test_money_fx.py`, `test_foundation_api.py` |
| US-CAPTURE-05 | Done | `PATCH /expenses/{id}`, `DELETE /expenses/{id}` | `/expenses` | `test_expenses_api.py` |
| US-CAPTURE-06 | Done | `GET /expenses` (filters) | `/expenses` | `test_expenses_api.py` |
| US-BUDGET-01 | Done | `GET/PUT /budgets`, `DELETE /budgets/{id}`, `GET /budgets/status` | `/budgets` | `test_money_budgets.py`, `test_money_tools.py` |
| US-BUDGET-02 | Done | `POST /expenses` (warnings) | `/expenses`, `/` | `test_money_budgets.py`, `test_integration.py` |
| US-BUDGET-03 | Done | `GET /dashboard` | `/` | `test_money_dashboard.py` |
| US-BUDGET-04 | Done | `GET /subscriptions`, `POST /subscriptions/detect`, `GET /subscriptions/upcoming`, `POST /subscriptions/{id}/dismiss` | `/subscriptions`, `/` | `test_money_subscriptions.py` |
| US-BUDGET-05 | Partial | `POST /chat` | `/chat` | `test_money_tools.py`, evals |
| US-HOUSE-01 | Done | `POST/GET /houses`, `POST /houses/{id}/members` | `/houses` | `test_api.py` |
| US-HOUSE-02 | Not started | none | none | none |
| US-HOUSE-03 | Done | `POST /houses/{id}/expenses` | `/houses` | `test_settlement.py`, `test_api.py` |
| US-HOUSE-04 | Done | `POST /houses/{id}/expenses/split` | `/houses` | `test_house_api.py`, `test_house_splits.py` |
| US-HOUSE-05 | Done | `GET /houses/{id}/balances` | `/houses`, `/` | `test_settlement.py`, `test_house_api.py` |
| US-HOUSE-06 | Done | `GET/POST /houses/{id}/settlements`, `DELETE /houses/{id}/settlements/{id}` | `/houses` | `test_house_api.py`, `test_foundation_api.py` |
| US-HOUSE-07 | Partial | `GET/POST /houses/{id}/reminders`, `PATCH /houses/{id}/reminders/{id}` | `/houses` | `test_house_reminders.py` (fakes) |
| US-HOUSE-08 | Done | `DELETE /houses/{id}/members/{user_id}`, `DELETE /houses/{id}/expenses/{id}` | `/houses` | `test_house_members.py` |
| US-HOUSE-09 | Partial | `POST /chat` | `/chat` | `test_house_tools.py`, `test_live.py` (live only) |
| US-ASK-01 | Partial | `POST /chat` | `/chat` | `test_agents_offline.py`, `test_reports.py`, `test_report_guard.py`, evals |
| US-ASK-02 | Done | `POST /chat` | `/chat`, `/` | `test_integration.py`, `test_report_guard.py` |
| US-ASK-03 | Done | `POST /chat` | `/chat` | `test_report_checker.py` |
| US-ASK-04 | Partial | `POST /chat` | `/chat` | `test_integration.py`, evals |
| US-ASK-05 | Partial | `POST /chat` | `/chat` | `test_agents_offline.py`, evals |
| US-ASK-06 | Partial | `POST /chat`, `POST /receipts` | `/chat`, `/receipts` | `test_live.py` (live only), evals |
| US-INBOX-01 | Done | `POST /imports/statement` | `/import` | `test_ingest_statements.py` |
| US-INBOX-02 | Partial | `POST /imports/statement` | `/import` | `test_ingest_statements.py` (fake), `test_ingest_live.py` (live only) |
| US-INBOX-03 | Done | `GET /inbox`, `PATCH /inbox/{id}`, `POST /inbox/{id}/approve`, `POST /inbox/{id}/reject`, `POST /inbox/approve`, `POST /inbox/reject` | `/inbox` | `test_ingest_inbox.py` |
| US-INBOX-04 | Partial | `/integrations/google/*`, `POST /internal/gmail/push`, `POST /internal/gmail/sync-all` | `/settings`, `/inbox` | `test_ingest_oauth.py`, `test_ingest_sync.py`, `test_ingest_gmail.py` (fakes) |
| US-INBOX-05 | Partial | `POST /chat` | `/chat` | `test_ingest_inbox.py`, `test_ingest_sync.py`, evals |
| US-GUARD-01 | Done | all | all | `test_api.py`, `test_expenses_api.py`, `test_report_guard.py` |
| US-GUARD-02 | Done | `POST /chat` | `/chat` | `test_reports.py`, `test_report_guard.py`, evals `refusal-*` |
| US-GUARD-03 | Done | `POST /chat`, `POST /receipts`, Gmail sync | `/chat`, `/inbox` | `test_ingest_sync.py`, `test_report_checker.py` |
| US-GUARD-04 | Partial | all (SQL Server only) | none | `test_migrations.py` (offline DDL) |
| US-GUARD-05 | Done | every money endpoint | all | `test_house_splits.py`, `test_settlement.py`, `test_money_fx.py` |
| US-GUARD-06 | Done | `/integrations/google/*` | `/settings` | `test_ingest_oauth.py`, `test_categories_crypto.py` |
| US-GUARD-07 | Not started | `POST /chat`, `POST /receipts` | none | none |
| US-GUARD-08 | Not started | none | none | none |
| US-ACCOUNT-01 | Partial | every endpoint (Bearer token) | nav bar | `test_foundation_api.py` (faked verifier) |
| US-ACCOUNT-02 | Done | every endpoint (`X-User-Id`) | nav bar | `test_api.py` |
| US-ACCOUNT-03 | Done | `GET/PATCH /me` | `/settings` | `test_expenses_api.py` |
| US-ACCOUNT-04 | Partial | `GET /health` | all | none (deploy scripts dry-run only) |

## Open stories (future issues)

Partial:

- US-CAPTURE-02 Save a receipt from a photo: verify receipt vision on Gemini.
- US-CAPTURE-03 Tell the chat about a purchase: verify on Gemini.
- US-BUDGET-05 Budgets, subscriptions and rates in chat: fix the reply language, verify on
  Gemini.
- US-HOUSE-07 Settle-up reminders: run Calendar against real Google.
- US-HOUSE-09 Run the house from the chat: verify on Gemini.
- US-ASK-01 Spending questions with charts: verify on Gemini.
- US-ASK-04 Answers in my language: fix the failing case, measure on Gemini.
- US-ASK-05 Routing: verify on Gemini.
- US-ASK-06 Kasa runs on Gemini: live tests and evals with `gemini-3.5-flash-lite`.
- US-INBOX-02 PDF statements: record a live run.
- US-INBOX-04 Gmail: create the OAuth client and consent screen, run the real flow.
- US-INBOX-05 Inbox in chat: verify on Gemini.
- US-GUARD-04 Row-level security: run the migrations on Azure SQL and the RLS smoke test.
- US-ACCOUNT-01 Google sign-in: configure Firebase.
- US-ACCOUNT-04 Public address: first Cloud Run deploy.

Not started:

- US-HOUSE-02 Invite a flatmate with a link.
- US-GUARD-07 Limit chat use per user.
- US-GUARD-08 Delete my account and data.
