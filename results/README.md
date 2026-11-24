### Reproduce M0 on the development split

M0 predicts the first sentence of the textbook context for each QA turn.
It uses PySBD to detect English sentence boundaries.

From the repository root, run:

```bash
python -m pip install -r requirements.txt
python -m src.baselines.lead_k --input data/splits/dev.jsonl --output results/m0_dev_predictions.jsonl --k 1
python -m src.evaluate --gold data/splits/dev.jsonl --pred results/m0_dev_predictions.jsonl --output results/m0_dev_scores.json
```

The first evaluation run downloads `roberta-large` for BERTScore.

| Method | Split | QA turns | Empty predictions | BLEU (0–100) | ROUGE-L F1 | BERTScore-F1 |
|---|---|---:|---:|---:|---:|---:|
| M0 (lead-1) | Dev | 534 | 0 | 0.30 | 0.1235 | 0.8545 |