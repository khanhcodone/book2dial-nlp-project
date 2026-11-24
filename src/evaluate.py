import argparse
import json
from importlib.metadata import version
from pathlib import Path
from statistics import mean

from bert_score import score as bert_score
from rouge_score import rouge_scorer
from sacrebleu.metrics import BLEU


def read_text_by_id(path, field):
    """Read a JSONL file and reject missing, invalid, or duplicate fields."""
    values = {}

    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            location = f"{path}, line {line_number}"
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{location}: invalid JSON") from error

            if not isinstance(row, dict):
                raise ValueError(f"{location}: expected a JSON object")

            sample_id = row.get("id")
            if not isinstance(sample_id, str) or not sample_id.strip():
                raise ValueError(f"{location}: missing or invalid id")
            if sample_id in values:
                raise ValueError(f"{location}: duplicate id {sample_id}")

            text = row.get(field)
            if not isinstance(text, str):
                raise ValueError(f"{location}: missing or invalid {field}")
            if field == "reference" and not text.strip():
                raise ValueError(f"{location}: empty reference for {sample_id}")

            values[sample_id] = text.strip()

    if not values:
        raise ValueError(f"{path}: no samples found")

    return values


def align_predictions(gold, predicted):
    """Return references and predictions in the same sample order."""
    missing = gold.keys() - predicted.keys()
    extra = predicted.keys() - gold.keys()

    if missing or extra:
        raise ValueError(
            f"ID mismatch: {len(missing)} missing, {len(extra)} extra. "
            f"Missing examples: {sorted(missing)[:3]}. "
            f"Extra examples: {sorted(extra)[:3]}."
        )

    references = list(gold.values())
    predictions = [predicted[sample_id] for sample_id in gold]
    return references, predictions


def evaluate(references, predictions, model, device, batch_size):
    bleu = BLEU(tokenize="13a", lowercase=False)
    bleu_value = bleu.corpus_score(predictions, [references]).score

    rouge = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    rouge_value = mean(
        rouge.score(reference, prediction)["rougeL"].fmeasure
        for reference, prediction in zip(references, predictions)
    )

    (_, _, f1), bert_hash = bert_score(
        predictions,
        references,
        model_type=model,
        lang="en",
        device=device,
        batch_size=batch_size,
        rescale_with_baseline=False,
        return_hash=True,
    )

    return {
        "n_samples": len(references),
        "n_empty_predictions": sum(not text for text in predictions),
        "BLEU": bleu_value,
        "ROUGE-L": rouge_value,
        "BERTScore-F1": f1.mean().item(),
        "config": {
            "bleu_signature": str(bleu.get_signature()),
            "rouge_use_stemmer": True,
            "bert_model": model,
            "bert_hash": bert_hash,
            "bert_device": device,
            "bert_batch_size": batch_size,
            "versions": {
                name: version(name)
                for name in ("sacrebleu", "rouge-score", "bert-score")
            },
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--pred", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bert-model", default="roberta-large")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()

    gold = read_text_by_id(args.gold, "reference")
    predicted = read_text_by_id(args.pred, "prediction")
    references, predictions = align_predictions(gold, predicted)

    result = evaluate(
        references, predictions, args.bert_model, args.device, args.batch_size
    )
    result["gold_file"] = str(args.gold)
    result["prediction_file"] = str(args.pred)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    output = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)
    args.output.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()