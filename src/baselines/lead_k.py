import argparse
import json
from pathlib import Path

import pysbd


def generate_predictions(input_path, k):
    segmenter = pysbd.Segmenter(language="en", clean=False)
    predictions = []
    seen_ids = set()

    with input_path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            row = json.loads(line)
            sample_id = row["id"]
            context = row["context"]

            if sample_id in seen_ids:
                raise ValueError(f"Duplicate id at line {line_number}: {sample_id}")
            if not isinstance(context, str) or not context.strip():
                raise ValueError(f"Empty or invalid context for {sample_id}")

            sentences = segmenter.segment(context.strip())
            prediction = " ".join(s.strip() for s in sentences[:k]).strip()
            if not prediction:
                raise ValueError(f"No sentence found for {sample_id}")

            predictions.append({"id": sample_id, "prediction": prediction})
            seen_ids.add(sample_id)

    if not predictions:
        raise ValueError(f"No samples found in {input_path}")

    return predictions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--k", type=int, default=1)
    args = parser.parse_args()

    if args.k < 1:
        parser.error("--k must be at least 1")

    predictions = generate_predictions(args.input, args.k)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", encoding="utf-8") as file:
        for row in predictions:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(predictions)} predictions to {args.output}")


if __name__ == "__main__":
    main()