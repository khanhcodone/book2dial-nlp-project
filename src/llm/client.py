"""Shared LLM client for every group script (sections 3, 4 and 6).

Talks to any OpenAI-compatible endpoint (default: OpenRouter) and adds what the
project rules require for LLM runs (project-rules.md section 8):
  * temperature 0 by default,
  * a JSON cache of every call (one file per call under ``cache/llm/``),
  * bounded retries (at most 3) instead of the original infinite loop,
  * a CSV log of tokens, cost, latency and errors per call,
  * summary statistics (error rate, time and cost per 1,000 calls).

Configuration comes from environment variables or a local ``.env`` file
(git-ignored): ``LLM_BASE_URL``, ``LLM_MODEL``, ``OPENROUTER_API_KEY``
(falls back to ``OPENAI_API_KEY``). Keys are never written to the cache or log.

Example:
    from src.llm import LLMClient
    client = LLMClient(model="meta-llama/llama-3.3-70b-instruct:free")
    result = client.chat("Say OK")
    print(result.text, result.cached, result.error)
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import openai
from dotenv import load_dotenv
from openai import OpenAI

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_CACHE_DIR = "cache/llm"
MAX_RETRIES = 3  # retries after the first attempt, so at most 4 calls
# Overload (429 rate limit, 5xx such as 503 "high demand"): free models need longer waits.
OVERLOAD_BACKOFF_SECONDS = (15, 30, 60)
# Network problems (timeout, connection reset): short waits are enough.
NETWORK_BACKOFF_SECONDS = (2, 4, 8)
MAX_RETRY_AFTER_SECONDS = 120  # cap for a server-sent Retry-After header

OVERLOAD_ERRORS = (openai.RateLimitError, openai.InternalServerError)
NETWORK_ERRORS = (openai.APITimeoutError, openai.APIConnectionError)
RETRYABLE_ERRORS = OVERLOAD_ERRORS + NETWORK_ERRORS

LOG_FIELDS = [
    "timestamp", "model", "cache_key", "cached", "prompt_tokens",
    "completion_tokens", "cost_usd", "latency_s", "wait_s", "attempts", "invalid", "error",
]


def append_csv_row(path: str | Path, fieldnames: list[str], row: dict) -> None:
    """Append one row; write the header for a new file. If an existing file has a
    different header (older code version), move it aside instead of mixing columns."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with path.open(encoding="utf-8") as f:
            header = f.readline().strip().split(",")
        if header != fieldnames:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            old = path.with_name(f"{path.stem}.old-{stamp}{path.suffix}")
            path.rename(old)
            print(f"  [log] {path.name} had an older header, moved to {old.name}")
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


@dataclass
class LLMResult:
    """Outcome of one chat call. ``error`` is set instead of raising."""

    text: str | None
    model: str
    cache_key: str
    cached: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float | None = None
    latency_s: float = 0.0  # time spent in API requests (all attempts), without retry waits
    wait_s: float = 0.0  # time slept between retries
    attempts: int = 0
    invalid: bool = False
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def ok(self) -> bool:
        return self.error is None and not self.invalid


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "model"


class LLMClient:
    """OpenAI-compatible chat client with cache, bounded retries and logging."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        cache_dir: str | Path | None = DEFAULT_CACHE_DIR,
        log_path: str | Path | None = None,
        timeout: float = 120.0,
        reasoning: bool | None = None,
    ) -> None:
        """``reasoning``: True/False turns the model's thinking mode on/off
        (OpenRouter ``reasoning.enabled``); None keeps the provider default."""
        load_dotenv()
        self.base_url = base_url or os.environ.get("LLM_BASE_URL") or DEFAULT_BASE_URL
        self.model = model or os.environ.get("LLM_MODEL")
        if not self.model:
            raise ValueError("No model given: pass model=... or set LLM_MODEL.")
        key = api_key or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "No API key found. Set OPENROUTER_API_KEY (or OPENAI_API_KEY) "
                "in the environment or in a local .env file."
            )
        self.host = urlparse(self.base_url).netloc
        self.is_openrouter = "openrouter.ai" in self.host
        self.reasoning = reasoning
        if reasoning is not None and not self.is_openrouter:
            raise ValueError("reasoning on/off is only implemented for OpenRouter; use None.")
        # max_retries=0: retries are handled here so that they stay bounded and logged.
        self._client = OpenAI(api_key=key, base_url=self.base_url, timeout=timeout, max_retries=0)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.log_path = Path(log_path) if log_path else None
        self._stats = {"calls": 0, "cached": 0, "errors": 0, "invalid": 0,
                       "prompt_tokens": 0, "completion_tokens": 0,
                       "cost_usd": 0.0, "api_seconds": 0.0, "wait_seconds": 0.0}

    # ------------------------------------------------------------------ cache
    @staticmethod
    def make_key(model: str, messages: list[dict], temperature: float,
                 max_tokens: int | None, reasoning: bool | None = None) -> str:
        payload = json.dumps(
            {"model": model, "messages": messages, "temperature": temperature,
             "max_tokens": max_tokens, "reasoning": reasoning},
            sort_keys=True, ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _cache_file(self, model: str, key: str) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / _slug(model) / f"{key}.json"

    # ------------------------------------------------------------------- call
    def chat(
        self,
        prompt: str | list[dict],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        seed: int | None = 42,
    ) -> LLMResult:
        """Send one chat request. ``prompt`` is a user string or a message list."""
        model = model or self.model
        messages = [{"role": "user", "content": prompt}] if isinstance(prompt, str) else prompt
        key = self.make_key(model, messages, temperature, max_tokens, self.reasoning)
        cache_file = self._cache_file(model, key)

        if cache_file is not None and cache_file.exists():
            entry = json.loads(cache_file.read_text(encoding="utf-8"))
            result = LLMResult(cached=True, **entry["result"])
            self._record(result)
            return result

        result = self._call_api(model, messages, key, temperature, max_tokens, seed)
        # Only successful calls are cached, so failed calls are retried on the next run.
        if cache_file is not None and result.error is None:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "base_url_host": self.host,
                "request": {"model": model, "messages": messages,
                            "temperature": temperature, "max_tokens": max_tokens,
                            "seed": seed, "reasoning": self.reasoning},
                "result": {k: v for k, v in asdict(result).items() if k != "cached"},
            }
            cache_file.write_text(json.dumps(entry, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        self._record(result)
        return result

    def _call_api(self, model, messages, key, temperature, max_tokens, seed) -> LLMResult:
        kwargs: dict[str, Any] = {"model": model, "messages": messages,
                                  "temperature": temperature}
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if seed is not None:
            kwargs["seed"] = seed
        if self.is_openrouter:
            extra: dict[str, Any] = {"usage": {"include": True}}  # returns cost in USD
            if self.reasoning is not None:
                extra["reasoning"] = {"enabled": self.reasoning}
            kwargs["extra_body"] = extra

        error = None
        start = time.perf_counter()
        waited = 0.0  # retry sleeps, kept out of latency so time per 1k calls is not inflated
        attempts = 0
        for retry in range(MAX_RETRIES + 1):
            attempts += 1
            try:
                completion = self._client.chat.completions.create(**kwargs)
                result = self._parse(completion, model, key,
                                     time.perf_counter() - start - waited, attempts)
                result.wait_s = round(waited, 3)
                return result
            except RETRYABLE_ERRORS as exc:
                error = f"{type(exc).__name__}: {exc}"
                if retry < MAX_RETRIES:
                    wait = self._wait_seconds(exc, retry)
                    print(f"  [llm] {type(exc).__name__}, retry {retry + 1}/{MAX_RETRIES} "
                          f"in {wait:.0f}s", flush=True)
                    slept_from = time.perf_counter()
                    time.sleep(wait)
                    waited += time.perf_counter() - slept_from  # measured, not nominal
            except openai.APIError as exc:  # 4xx such as bad key or bad model: no retry
                error = f"{type(exc).__name__}: {exc}"
                break
        return LLMResult(text=None, model=model, cache_key=key, error=error,
                         latency_s=round(time.perf_counter() - start - waited, 3),
                         wait_s=round(waited, 3), attempts=attempts)

    @staticmethod
    def _wait_seconds(exc: Exception, retry: int) -> float:
        """Wait before the next retry: Retry-After if the server sent it, else a fixed backoff."""
        if isinstance(exc, OVERLOAD_ERRORS):
            response = getattr(exc, "response", None)
            header = response.headers.get("retry-after") if response is not None else None
            try:
                if header is not None:
                    return min(max(float(header), 1.0), MAX_RETRY_AFTER_SECONDS)
            except ValueError:  # HTTP-date form: ignore and use the fixed backoff
                pass
            return OVERLOAD_BACKOFF_SECONDS[retry]
        return NETWORK_BACKOFF_SECONDS[retry]

    @staticmethod
    def _parse(completion, model, key, latency, attempt) -> LLMResult:
        raw = completion.model_dump()
        choices = raw.get("choices") or []
        text = (choices[0].get("message") or {}).get("content") if choices else None
        usage = raw.get("usage") or {}
        cost = usage.get("cost")
        if raw.get("error"):  # some providers return 200 with an error body
            return LLMResult(text=None, model=raw.get("model") or model, cache_key=key,
                             latency_s=round(latency, 3), attempts=attempt,
                             error=f"ProviderError: {raw['error']}")
        return LLMResult(
            text=text,
            model=raw.get("model") or model,
            cache_key=key,
            prompt_tokens=usage.get("prompt_tokens") or 0,
            completion_tokens=usage.get("completion_tokens") or 0,
            cost_usd=float(cost) if cost is not None else None,
            latency_s=round(latency, 3),
            attempts=attempt,
            invalid=not (text and text.strip()),
            raw={"id": raw.get("id"), "finish_reason": choices[0].get("finish_reason") if choices else None},
        )

    # --------------------------------------------------------------- logging
    def _record(self, result: LLMResult) -> None:
        s = self._stats
        s["calls"] += 1
        s["cached"] += int(result.cached)
        s["errors"] += int(result.error is not None)
        s["invalid"] += int(result.invalid)
        if not result.cached:
            s["prompt_tokens"] += result.prompt_tokens
            s["completion_tokens"] += result.completion_tokens
            s["cost_usd"] += result.cost_usd or 0.0
            s["api_seconds"] += result.latency_s
            s["wait_seconds"] += result.wait_s
        if self.log_path is None:
            return
        append_csv_row(self.log_path, LOG_FIELDS, {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": result.model, "cache_key": result.cache_key,
            "cached": result.cached, "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "cost_usd": "" if result.cost_usd is None else f"{result.cost_usd:.6f}",
            "latency_s": result.latency_s, "wait_s": result.wait_s,
            "attempts": result.attempts, "invalid": result.invalid, "error": result.error or "",
        })

    def stats(self) -> dict[str, Any]:
        """Totals for this client, including error rate and time/cost per 1,000 API calls.
        ``seconds_per_1k`` counts request time only; retry sleeps are in ``wait_seconds``."""
        s = dict(self._stats)
        api_calls = s["calls"] - s["cached"]
        s["api_calls"] = api_calls
        s["error_rate"] = s["errors"] / s["calls"] if s["calls"] else 0.0
        s["invalid_rate"] = s["invalid"] / s["calls"] if s["calls"] else 0.0
        if api_calls:
            s["seconds_per_1k"] = round(s["api_seconds"] / api_calls * 1000, 1)
            s["cost_usd_per_1k"] = round(s["cost_usd"] / api_calls * 1000, 4)
        s["cost_usd"] = round(s["cost_usd"], 6)
        s["api_seconds"] = round(s["api_seconds"], 1)
        s["wait_seconds"] = round(s["wait_seconds"], 1)
        return s
