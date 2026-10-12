"""Run the eval cases in cases.jsonl against the configured LLM provider.

    cd backend
    LLM_PROVIDER=ollama OLLAMA_BASE_URL=http://<host>:11434 python -m evals.run_evals [--only route-]

Each case is one /chat turn for a fresh user with seeded demo data. A case passes when the
expected agent answered, the expected tool was called, and (for reports) the chart and
numbers match the seeded data. Results go to stdout as one JSON line per case plus a
summary, so runs on different models can be compared.

Case fields: id, message, expect_agent, expect_tool, expect_chart (optional),
expect_no_rows_from (optional, a table that must never appear in results).

Owner: track REPORT. The loader and the CLI are here; seeding and scoring are TODO.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

CASES = Path(__file__).with_name("cases.jsonl")


@dataclass
class EvalCase:
    id: str
    message: str
    expect_agent: str
    expect_tool: str | None = None
    expect_chart: str | None = None
    expect_no_rows_from: str | None = None


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    seconds: float
    agent: str | None
    tools: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def load_cases(path: Path = CASES, only: str | None = None) -> list[EvalCase]:
    cases = [
        EvalCase(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    return [c for c in cases if not only or c.id.startswith(only)]


def seed_demo_data(user_id: str) -> None:
    """Create a house with flatmates and a month of expenses for `user_id`."""
    raise NotImplementedError("seed_demo_data: track REPORT")


async def run_case(case: EvalCase) -> EvalResult:
    """seed_demo_data for a fresh user, runtime.run_agent("chat", ...), then score."""
    raise NotImplementedError("run_case: track REPORT")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="run cases whose id starts with this prefix")
    args = parser.parse_args()
    cases = load_cases(only=args.only)
    print(f"{len(cases)} cases loaded; scoring is not implemented yet (track REPORT)")


if __name__ == "__main__":
    main()
