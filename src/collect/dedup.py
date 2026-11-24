import argparse
import hashlib
import json
import re
from pathlib import Path


def normalize_for_dedup(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def text_hash(text: str) -> str:
    return hashlib.sha256(normalize_for_dedup(text).encode("utf-8")).hexdigest()


def collect_existing_hashes(textbook_dir: Path, generated_dir: Path) -> set[str]:
    hashes: set[str] = set()

    if textbook_dir.exists():
        for json_file in textbook_dir.glob("*.json"):
            try:
                content = json.loads(json_file.read_text(encoding="utf-8"))
                for sec in content.get("data", []):
                    paras = sec.get("paragraphs", [])
                    if paras and paras[0].get("context"):
                        hashes.add(text_hash(paras[0]["context"]))
            except Exception:
                continue

    if generated_dir.exists():
        for jsonl_file in generated_dir.glob("*.jsonl"):
            try:
                for line in jsonl_file.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if row.get("context"):
                        hashes.add(text_hash(row["context"]))
            except Exception:
                continue

    return hashes


def deduplicate_sections(
    input_json: Path,
    output_json: Path,
    textbook_dir: Path,
    generated_dir: Path,
) -> dict:
    raw = json.loads(input_json.read_text(encoding="utf-8"))
    sections = raw.get("data", [])
    in_count = len(sections)

    existing_hashes = collect_existing_hashes(textbook_dir, generated_dir)
    seen_batch_hashes: set[str] = set()
    seen_titles: set[str] = set()

    kept: list[dict] = []
    dropped_existing = 0
    dropped_duplicate = 0

    for sec in sections:
        title = (sec.get("title") or "").strip().lower()
        paras = sec.get("paragraphs", [])
        context = paras[0].get("context", "") if paras else ""
        h = text_hash(context)

        if h in existing_hashes:
            dropped_existing += 1
            continue
        if h in seen_batch_hashes or (title and title in seen_titles):
            dropped_duplicate += 1
            continue

        seen_batch_hashes.add(h)
        if title:
            seen_titles.add(title)
        kept.append(sec)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps({"data": kept}, indent=2, ensure_ascii=False), encoding="utf-8")

    stats = {
        "in_count": in_count,
        "out_count": len(kept),
        "dropped_existing": dropped_existing,
        "dropped_duplicate": dropped_duplicate,
    }
    print(
        f"Dedup stats: in={in_count}, out={len(kept)}, "
        f"dropped_existing={dropped_existing}, dropped_duplicate={dropped_duplicate}"
    )
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Deduplicate parsed textbook sections.")
    parser.add_argument("--input-json", type=Path, default=Path("data/raw_openstax/biology_2e_parsed.json"))
    parser.add_argument("--output-json", type=Path, default=Path("data/raw_openstax/biology_2e_dedup.json"))
    parser.add_argument("--textbook-dir", type=Path, default=Path("example_textbook_data"))
    parser.add_argument("--generated-dir", type=Path, default=Path("generated_dataset"))
    args = parser.parse_args()

    deduplicate_sections(
        input_json=args.input_json,
        output_json=args.output_json,
        textbook_dir=args.textbook_dir,
        generated_dir=args.generated_dir,
    )


if __name__ == "__main__":
    main()