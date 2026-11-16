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

Rules: every script takes input and output paths as arguments, uses seed 42, and never contains a key.
See `.claude/rules/project-rules.md`.
