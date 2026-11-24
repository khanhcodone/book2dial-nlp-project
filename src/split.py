import argparse
import json
import random
from pathlib import Path

from src.normalize import normalize


DOMAINS = ("business", "math", "science", "social")
SPLITS = ("train", "dev", "test")


def load_dialogues(domain, textbooks_dir, dialogues_dir):
    book_path = textbooks_dir / f"{domain}_train_full.json"
    dialogue_path = dialogues_dir / f"{domain}_Persona_high_info.jsonl"

    sections = json.loads(book_path.read_text(encoding="utf-8"))["data"]
    with dialogue_path.open(encoding="utf-8") as file:
        dialogues = [json.loads(line) for line in file if line.strip()]

    if len(sections) != len(dialogues):
        raise ValueError(f"{domain}: textbook and dialogue counts differ")

    records = []
    for position, (section, dialogue) in enumerate(zip(sections, dialogues), 1):
        if section["title"] != dialogue["title"]:
            raise ValueError(f"{domain}: title mismatch at record {position}")

        paragraph = section["paragraphs"][0]
        records.append({
            "uid": dialogue["uid"],
            "domain": domain,
            "section_id": paragraph["id"],
            "title": section["title"],
            "context": paragraph["context"],
            "qas": dialogue["qas"],
        })

    return records


def split_dialogues(records, rng):
    ordered = sorted(records, key=lambda record: record["uid"])
    rng.shuffle(ordered)

    n_dev = round(len(ordered) * 0.1)
    n_test = round(len(ordered) * 0.1)
    n_train = len(ordered) - n_dev - n_test
    dev_end = n_train + n_dev

    return {
        "train": ordered[:n_train],
        "dev": ordered[n_train:dev_end],
        "test": ordered[dev_end:],
    }


def make_turns(record):
    history = []

    for turn, qa in enumerate(record["qas"], start=1):
        sample_id = f"{record['uid']}-t{turn:02d}"
        question = normalize(qa["question"], "question")
        answer = normalize(qa["answer"]["text"], "answer")

        if not question or not answer:
            raise ValueError(f"{sample_id}: empty question or answer")

        yield {
            "id": sample_id,
            "uid": record["uid"],
            "domain": record["domain"],
            "section_id": record["section_id"],
            "title": record["title"],
            "context": record["context"],
            "history": history.copy(),
            "question": question,
            "reference": answer,
        }

        history.append({"question": question, "answer": answer})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--textbooks", type=Path, required=True)
    parser.add_argument("--dialogues", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--exclude-uid", action="append", default=[])
    args = parser.parse_args()

    rng = random.Random(args.seed)
    excluded = set(args.exclude_uid)
    seen_uids = set()
    rows = {name: [] for name in SPLITS}

    print("domain     input  excluded  train  dev  test  (dialogues)")
    for domain in DOMAINS:
        records = load_dialogues(domain, args.textbooks, args.dialogues)

        for record in records:
            uid = record["uid"]
            if uid in seen_uids:
                raise ValueError(f"Duplicate dialogue uid: {uid}")
            seen_uids.add(uid)

        kept = [record for record in records if record["uid"] not in excluded]
        parts = split_dialogues(kept, rng)
        print(
            f"{domain:9} {len(records):6} {len(records) - len(kept):9}"
            f" {len(parts['train']):6} {len(parts['dev']):4} {len(parts['test']):5}"
        )

        for name, dialogues in parts.items():
            for dialogue in dialogues:
                rows[name].extend(make_turns(dialogue))

    unknown = excluded - seen_uids
    if unknown:
        raise ValueError(f"Unknown excluded uid(s): {sorted(unknown)}")

    args.output.mkdir(parents=True, exist_ok=True)
    for name, samples in rows.items():
        path = args.output / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as file:
            for sample in samples:
                file.write(json.dumps(sample, ensure_ascii=False) + "\n")
        print(f"{path}: {len(samples)} QA pairs")


if __name__ == "__main__":
    main()