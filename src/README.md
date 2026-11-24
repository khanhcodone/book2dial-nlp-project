# src/

Source code written by the group. The paper's original code stays in `Persona_models/` and `metrics/`.
Run scripts from the repository root, for example `python -m src.split`.

| Module | Purpose | Planned owner |
|---|---|---|
| `normalize.py` | shared text normalization used by every method | A |
| `split.py` | 80/10/10 split by dialogue, stratified by domain, seed 42 | A |
| `evaluate.py` | BLEU (sacrebleu), ROUGE-L, BERTScore | A |
| `convert_for_metrics.py` | convert dialogues to `{context, dialogue}` for `metrics/` | D |
| `baselines/` | `lead_k.py`, `tfidf.py` (A) · `w2v_rf.py` (B) · `bilstm.py` (C) · `t5.py` (D) | A, B, C, D |
| `llm/` | `client.py` (wrapper: base_url, temperature 0, cache, retry, cost log), `zero_shot.py` (B), `few_shot.py` (C) | C, B |
| `collect/` | `crawl_openstax.py`, `parse.py`, `generate_dialogs.py`; dedup script | B, C |
| `annotate/` | `llm_judge.py` (LLM labeling), `kappa.py` (agreement) | C |

## LLM client and dialogue generation (done)
Put `OPENROUTER_API_KEY` (and optionally `LLM_MODEL`) in a local `.env` (see `.env.example`), then:
```bash
pip install -r requirements.txt
# Generate Persona dialogues (info level high | medium | low), 6 QA pairs per subsection
python -m src.collect.generate_dialogs --input example_textbook_data/example.json \
    --output data/group/raw/example_high.jsonl --info high --model <model-id> --limit 2
# --reasoning off (default) | on | default : the model's thinking mode, recorded in the output
python -m src.collect.generate_dialogs --check-prompts                 # prompts identical to Persona_models/
python -m src.collect.generate_dialogs --dump-prompts prompts/persona_v1
```
In other scripts: `from src.llm import LLMClient; LLMClient(model=...).chat(prompt)` returns an `LLMResult`
(text, tokens, cost, latency, cached, error). Calls use temperature 0, are cached in `cache/llm/` (git-ignored),
are retried at most 3 times, and are logged to the CSV given as `log_path` (`results/llm_calls.csv` in the generator).

Rules: every script takes input and output paths as arguments, uses seed 42, and never contains a key.
See `.claude/rules/project-rules.md`.
