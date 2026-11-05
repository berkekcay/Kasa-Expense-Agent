"""Point Kasa at the fastest of several Ollama servers. Run it from backend/ before a demo:

    python -m scripts.pick_ollama                       # servers from OLLAMA_CANDIDATES in .env
    python -m scripts.pick_ollama http://host-a:11434 http://host-b:11434

For each server it checks that the chat model (OLLAMA_MODEL) and the receipt model
(OLLAMA_VISION_MODEL) are there, then times one short answer with a long prompt, which is
what a chat turn looks like (our instructions are a few thousand tokens). The fastest server
that has both models is written to OLLAMA_BASE_URL in .env. Restart the backend afterwards.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import httpx

from app.config import get_settings

ENV = Path(".env")
# About 3,000 tokens, roughly one agent's instructions. Varies per run so no cache helps.
FILLER = "Kasa tracks student spending in Turkish lira; every amount comes from a tool. " * 200


def _models(client: httpx.Client, url: str) -> set[str]:
    names = {m["name"] for m in client.get(f"{url}/api/tags").json().get("models", [])}
    return names | {n.removesuffix(":latest") for n in names}


def _time_answer(client: httpx.Client, url: str, model: str) -> float:
    start = time.perf_counter()
    r = client.post(
        f"{url}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": f"{time.time()} {FILLER}"},
                {"role": "user", "content": "Reply with OK."},
            ],
            "stream": False,
            "think": "low",
            "keep_alive": get_settings().ollama_keep_alive,
            "options": {"num_predict": 16},
        },
    )
    r.raise_for_status()
    return time.perf_counter() - start


def measure(url: str, model: str, vision: str) -> float | None:
    url = url.rstrip("/")
    try:
        with httpx.Client(timeout=httpx.Timeout(180.0, connect=5.0)) as client:
            models = _models(client, url)
            missing = [
                m
                for m in (model, vision)
                if m and m not in models and m.removesuffix(":latest") not in models
            ]
            if missing:
                print(f"  {url}: missing {', '.join(missing)}")
                return None
            _time_answer(client, url, model)  # loads the model if it was not in memory
            seconds = _time_answer(client, url, model)
    except (httpx.HTTPError, ValueError) as exc:
        print(f"  {url}: not reachable ({type(exc).__name__})")
        return None
    print(f"  {url}: {seconds:.1f} s for a chat-sized prompt")
    return seconds


def write_env(url: str) -> None:
    text = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    line = f"OLLAMA_BASE_URL={url}"
    if re.search(r"^OLLAMA_BASE_URL=.*$", text, flags=re.MULTILINE):
        text = re.sub(r"^OLLAMA_BASE_URL=.*$", line, text, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + "\n" + line + "\n"
    ENV.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("urls", nargs="*", help="Ollama base URLs (default: OLLAMA_CANDIDATES)")
    parser.add_argument("--dry-run", action="store_true", help="measure only, do not change .env")
    args = parser.parse_args()
    settings = get_settings()
    urls = args.urls or [u.strip() for u in settings.ollama_candidates.split(",") if u.strip()]
    if not urls:
        parser.error("give the server URLs, or set OLLAMA_CANDIDATES=url1,url2 in .env")
    print(f"Chat model {settings.ollama_model}, receipt model {settings.ollama_vision_model}")
    timings = {
        url.rstrip("/"): measure(url, settings.ollama_model, settings.ollama_vision_model) for url in urls
    }
    usable = {url: s for url, s in timings.items() if s is not None}
    if not usable:
        print("No server has both models. Pull them, or change OLLAMA_MODEL / OLLAMA_VISION_MODEL.")
        return 1
    best = min(usable, key=usable.__getitem__)
    if args.dry_run:
        print(f"Fastest: {best}")
    else:
        write_env(best)
        print(f"OLLAMA_BASE_URL={best} written to .env. Restart the backend.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
