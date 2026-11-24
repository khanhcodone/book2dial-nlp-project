"""Generate student-teacher dialogues from textbook subsections (Persona method).

Group rewrite of ``Persona_models/Persona_{high,medium,low}_info_final.py``:
same prompts (see ``persona_prompts.py``) and the same loop, plus
  * any OpenAI-compatible API through ``src.llm.LLMClient`` (OpenRouter by default),
    temperature 0, cache, at most 3 retries, cost / time log;
  * input, output, model and info level as command-line arguments;
  * resume by ``section_index`` (not by counting lines);
  * output in the released dataset schema (title, history, qas, uid) plus context
    and traceability fields; incomplete dialogues go to ``<output>.failed.jsonl``;
  * a row of in/out counts appended to ``results/pipeline_stats.csv``.

Examples (run from the repository root):
    python -m src.collect.generate_dialogs --input example_textbook_data/example.json \
        --output data/group/raw/example_high.jsonl --info high --model <model-id> --limit 2
    python -m src.collect.generate_dialogs --dump-prompts prompts/persona_v1
    python -m src.collect.generate_dialogs --check-prompts
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.collect.persona_prompts import (
    INFO_LEVELS, PROMPT_VERSION, format_history, section_fields, student_prompt, teacher_prompt,
)

# "off" by default: the paper used GPT-3.5, which has no thinking mode.
REASONING_CHOICES = {"off": False, "on": True, "default": None}
UID_NAMESPACE = uuid.UUID("6f1c2d1e-7b2a-4c55-9a8e-b00c2d1a0001")  # fixed, for reproducible uids
STATS_FIELDS = ["timestamp", "step", "input", "output", "info_level", "model",
                "sections_in", "skipped_done", "dialogues_out", "failed",
                "api_calls", "cached_calls", "prompt_tokens", "completion_tokens",
                "cost_usd", "api_seconds", "wait_seconds"]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def generate_dialog(client, section: dict, info_level: str, turns: int) -> tuple[list, list]:
    """Run the student/teacher loop for one subsection. Returns (pairs, errors)."""
    fields = section_fields(section)
    pairs: list[tuple[str, str]] = []
    for turn in range(turns // 2):
        history = format_history(pairs)
        q = client.chat(student_prompt(fields, history, info_level))
        if not q.ok:
            return pairs, [{"turn": turn, "role": "student", "error": q.error or "empty output"}]
        a = client.chat(teacher_prompt(fields, history, q.text))
        if not a.ok:
            return pairs, [{"turn": turn, "role": "teacher", "error": a.error or "empty output"}]
        pairs.append((q.text, a.text))
    return pairs, []


def build_record(section, idx, pairs, errors, args, client) -> dict:
    history = [text for pair in pairs for text in pair]
    uid_seed = f"{Path(args.input).name}|{idx}|{args.info}|{client.model}|{PROMPT_VERSION}"
    return {
        "title": section["title"],
        "context": section["paragraphs"][0]["context"],
        "history": history,
        "qas": [{"question": q, "answer": {"text": a}} for q, a in pairs],
        "uid": str(uuid.uuid5(UID_NAMESPACE, uid_seed)),
        "section_index": idx,
        "info_level": args.info,
        "synthetic": True,
        "generator": {
            "method": f"Persona {args.info} info",
            "model": client.model,
            "api_host": client.host,
            "temperature": 0.0,
            "reasoning": args.reasoning,
            "prompt_version": PROMPT_VERSION,
            "date": datetime.now(timezone.utc).date().isoformat(),
        },
        "errors": errors,
    }


def write_failed(path: Path, failed: dict[int, dict]) -> None:
    """Rewrite the failed file: one record per section (the latest failure), none if empty."""
    if not failed:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for idx in sorted(failed):
            f.write(json.dumps(failed[idx], ensure_ascii=False) + "\n")
    tmp.replace(path)


def run(args) -> int:
    from src.llm import LLMClient  # imported here so --dump/--check work without a key
    from src.llm.client import append_csv_row

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))["data"]
    end = len(data) if args.limit is None else min(len(data), args.start + args.limit)
    indices = range(args.start, end)
    output = Path(args.output)
    failed_path = output.with_name(output.stem + ".failed.jsonl")
    done = {r["section_index"] for r in read_jsonl(output)}
    # Latest failure per section; sections that are already done are dropped.
    failed = {r["section_index"]: r for r in read_jsonl(failed_path)
              if r["section_index"] not in done}
    write_failed(failed_path, failed)  # also removes duplicates left by older runs

    client = LLMClient(model=args.model, base_url=args.base_url,
                       cache_dir=args.cache_dir, log_path=args.log,
                       reasoning=REASONING_CHOICES[args.reasoning])
    print(f"model={client.model} host={client.host} info={args.info} reasoning={args.reasoning} "
          f"sections {args.start}..{end - 1} ({len(indices)}), already done: "
          f"{len(done & set(indices))}")

    n_out = n_failed = n_skipped = 0
    start_time = time.perf_counter()
    for idx in indices:
        if idx in done:
            n_skipped += 1
            continue
        pairs, errors = generate_dialog(client, data[idx], args.info, args.turns)
        record = build_record(data[idx], idx, pairs, errors, args, client)
        if errors:
            n_failed += 1
            failed[idx] = record
            write_failed(failed_path, failed)
            print(f"[{idx}] FAILED after {len(pairs)} pairs: {errors[0]['error'][:200]}")
        else:
            n_out += 1
            append_jsonl(output, record)
            if failed.pop(idx, None) is not None:
                write_failed(failed_path, failed)
            print(f"[{idx}] ok ({len(pairs)} pairs) {data[idx]['title']}")

    s = client.stats()
    print(f"done in {time.perf_counter() - start_time:.1f}s | out={n_out} failed={n_failed} "
          f"skipped={n_skipped} | {json.dumps(s)}")
    if args.stats_csv:
        append_csv_row(args.stats_csv, STATS_FIELDS, {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "step": "generate_dialogs", "input": args.input, "output": args.output,
            "info_level": args.info, "model": client.model, "sections_in": len(indices),
            "skipped_done": n_skipped, "dialogues_out": n_out, "failed": n_failed,
            "api_calls": s["api_calls"], "cached_calls": s["cached"],
            "prompt_tokens": s["prompt_tokens"], "completion_tokens": s["completion_tokens"],
            "cost_usd": s["cost_usd"], "api_seconds": s["api_seconds"],
            "wait_seconds": s["wait_seconds"],
        })
    return 1 if n_failed else 0


# ---------------------------------------------------------------- prompt tools
PLACEHOLDER_SECTION = {
    "title": "{chapter_title}", "section_title": "{section_title}",
    "paragraphs": [{"context": "{context}"}], "chapter_summary": "{chapter_summary}",
    "bold_terms": ["{bold_terms}"], "chapter_learning_objectives": ["{learning_objectives}"],
    "chapter_concept": [{"name": "{concepts}"}], "chapter_introduction": "{introduction}",
}


def dump_prompts(out_dir: Path) -> None:
    """Write the prompt templates as text files (for the report appendix)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    f = section_fields(PLACEHOLDER_SECTION)
    for level in INFO_LEVELS:
        (out_dir / f"student_{level}.txt").write_text(
            student_prompt(f, "{previous_conversation}", level) + "\n", encoding="utf-8")
    (out_dir / "teacher.txt").write_text(
        teacher_prompt(f, "{previous_conversation}", "{question}") + "\n", encoding="utf-8")
    print(f"wrote {len(INFO_LEVELS) + 1} prompt files to {out_dir}")


def check_prompts(input_path: str) -> int:
    """Compare our prompts with the original Persona functions on real sections."""
    import importlib.util
    import os

    os.environ.setdefault("OPENAI_API_KEY", "dummy-not-used")  # originals build a client at import
    section = json.loads(Path(input_path).read_text(encoding="utf-8"))["data"][0]
    f = section_fields(section)
    hist = format_history([("Q1?", "A1."), ("Q2?", "A2.")])
    ok = True
    for level in INFO_LEVELS:
        spec = importlib.util.spec_from_file_location(
            f"orig_{level}", f"Persona_models/Persona_{level}_info_final.py")
        orig = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(orig)
        args = (f["chapter_title"], f["section_title"], f["chapter_summary"], f["bold_terms"],
                f["learning_objectives"], f["concepts"], f["introduction"], hist)
        same_s = orig.generate_prompt1(*args) == student_prompt(f, hist, level)
        same_t = orig.generate_prompt2(f["chapter_title"], f["section_title"], f["context"],
                                       *args[2:], "Why?") == teacher_prompt(f, hist, "Why?")
        print(f"{level:6s} student identical={same_s} teacher identical={same_t}")
        ok &= same_s and same_t
    return 0 if ok else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--input", default="example_textbook_data/example.json",
                   help="textbook JSON in the example_textbook_data format")
    p.add_argument("--output", help="output JSONL (one dialogue per line)")
    p.add_argument("--info", choices=INFO_LEVELS, default="high", help="student info level")
    p.add_argument("--model", help="model id (default: $LLM_MODEL)")
    p.add_argument("--base-url", help="API base URL (default: $LLM_BASE_URL or OpenRouter)")
    p.add_argument("--reasoning", choices=REASONING_CHOICES, default="off",
                   help="model thinking mode: off (default, like GPT-3.5 in the paper), "
                        "on, or default (provider default)")
    p.add_argument("--turns",type=int, default=12, help="turns per dialogue (12 = 6 QA pairs)")
    p.add_argument("--start", type=int, default=0, help="first section index")
    p.add_argument("--limit", type=int, help="number of sections to process")
    p.add_argument("--cache-dir", default="cache/llm")
    p.add_argument("--log", default="results/llm_calls.csv", help="per-call CSV log")
    p.add_argument("--stats-csv", default="results/pipeline_stats.csv")
    p.add_argument("--dump-prompts", metavar="DIR", help="write prompt templates and exit")
    p.add_argument("--check-prompts", action="store_true",
                   help="check prompts against the original scripts and exit")
    args = p.parse_args(argv)

    if args.dump_prompts:
        dump_prompts(Path(args.dump_prompts))
        return 0
    if args.check_prompts:
        return check_prompts(args.input)
    if not args.output:
        p.error("--output is required")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
