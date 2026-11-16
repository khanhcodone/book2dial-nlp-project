# Project Rules: CSC15011 final project (Book2Dial)

> Sources: the course guideline `2026_DoAn_HuongDan_CSC15011.pdf` (lecturer Le Thanh Tung), the lecturer's own notes, and the Book2Dial paper (ACL 2024 Findings).
> Everything in this repository must follow this file. On conflict, priority is: lecturer requirements > this file > coding habits.
> Sections 1-11 are the course requirements. Sections 12-16 are the team's working rules.

## 1. The task (must not be changed)
- Paper: **Book2Dial: Generating Teacher-Student Interactions from Textbooks for Cost-Effective Development of Educational Chatbots** (Wang et al., ACL 2024 Findings, pp. 9707-9731).
- Output type: **text generation** (text to text), not classification.
  - Dialogue generation: `f(textbook subsection S, formatting C) -> d = {(q1,a1),...,(qT,aT)}`, T = 6 pairs (12 turns).
  - Student: `p_stu(q_t | C, h<t)`. Sees formatting only (title / summary / bold terms / objectives / concepts / introduction).
  - Teacher: `p_tea(a_t | S, h<t, q_t)`. Sees the full subsection text plus formatting.
  - Downstream task (paper section 5.4): generate the teacher answer `a_t` from `(S, h<t, q_t)`. Metric: BLEU (sacrebleu).
- Dataset language: **English** (OpenStax). Use English bert-base / roberta / T5 models. Do NOT use PhoBERT unless it is part of an optional Vietnamese extension.

## 2. Required data formats (keep the paper's field names)
- Textbook input (`example_textbook_data/*.json`): `{"data":[{title, paragraphs:[{context,id}], section_title, chapter_learning_objectives[], chapter_summary, chapter_introduction, bold_terms[], chapter_concept:[{name,description}]}]}`.
- Released dialogue dataset (`generated_dataset/*.jsonl`): each line is `{title, history:[q1,a1,q2,a2,...], qas, uid}`.
- The group dataset (section 4) MUST be JSONL, one dialogue per line. Keep the original fields `title, history, qas, uid`, add `context`, and add traceability fields:
  `id` (format `gXX_<member code>_0001`), `source` (OpenStax book + URL + license), `generator` (model, call date), `annotator`, `labels` (scores for the 7 criteria per QA pair), `llm_labels`, `date`.
- The scripts in `metrics/` read `{context, dialogue:[q,a,...]}`. A single shared conversion script is required; never convert by hand.

## 3. Required criteria and metrics (as in the paper)
| Criterion | Automatic metric | Note |
|---|---|---|
| Answer Relevance | BF1(q_t,a_t), QuestEval, Uptake | Uptake has no code in the repo |
| Informativeness | 1 - Overlap(a_t, a<t) | |
| Groundedness | Density, Coverage | |
| Coherence | BF1(q_t,a<t), BF1(q_t,a_{t-1}) | |
| Answerability | Answerable (distilbert SQuAD) | |
| Factual Consistency | QFactScore (alpha=beta=1) | |
| Specificity | manual annotation only | |
- Downstream (answer generation): **BLEU with sacrebleu** is the main metric for comparing with the paper. ROUGE-L and BERTScore are added.
- Manual annotation: the 7 yes/no/QA-pair questions of Table 12 in the paper. Report Cohen's kappa (2 annotators) or Fleiss' kappa (more). kappa > 0.6 is good, > 0.8 is very good.

## 4. Baseline numbers from the paper (for comparison only; NEVER adjust numbers to match)
- Table 2 (automatic, mean over 4 domains), Persona (High Info): BF1(q,a)=0.62, QuestEval=0.44, Uptake=0.99, 1-Overlap=0.60, Density=2.50, Coverage=0.71, BF1(q,a<t)=0.53, BF1(q,a_{t-1})=0.59, Answerable=0.99, QFactScore=0.75.
  Dialogue Inpainting: 1-Overlap=0.91, Density=22.62, Coverage=0.90 (highest because it copies textbook sentences). SimSeek: QFactScore=0.32.
- Table 3 (human), Persona High: AnsRel .97, Info .74, Gro .99, Coh .85, Fact .79, Ans .96, Spe .99. Fleiss kappa = 0.74 (4 annotators, 12 dialogues).
- Table 4 (downstream BLEU, FLAN-T5-Large): fine-tune on Social, test on CoQA-MCTest 26.30 (+4.16), CoQA-CNN 15.11 (+1.98); Business, test on NCTE 8.99 (+0.59); zero-shot 3.96 / 3.67 / 1.08.
- Dataset: 889 Persona High Info dialogues (math 142, business 123, science 228, social 396), 6 QA pairs per dialogue. Books: Introductory Statistics, Business Ethics, Physics, Psychology 2e.

## 5. Mandatory parts (8 points)
1. **Read and present the paper** (final presentation): the problem and why it is hard, 1-3 contributions, the method with redrawn figures, the experiments (data / baselines / metrics / results), limitations and the group's own critique.
2. **At least 3 basic NLP method families of DIFFERENT kinds** on the paper's dataset, with a fixed train/dev/test split, the same preprocessing (shared `normalize()`), the same metrics and one shared results table. Compare with the paper's numbers and explain the gap.
3. **At least 1 recent LLM method** (minimum: zero-shot through an API), on the same test set and metrics as part 2.
4. **Group sub-dataset: 250 samples per member** (4 members, 1,000 samples in total), same task, format and "label set" as the paper. It contains 4.1 the collection pipeline, 4.2 the labeling method, 4.3 statistics compared with the paper's dataset. The data must be NEW, not copied from the original dataset.

## 6. Optional parts (set the group apart)
5. Run parts 2-3 on the group dataset (train on paper data, test on group data; train and test on group data; LLM on group data).
6. Reproduce the paper's main method (Persona High / Medium / Low Info, official code available).
- Own ideas: error analysis (50 errors), robustness, data augmentation, ensembling, interpretability.

## 7. Grading criteria (in priority order)
1. **Number of different method families**: statistics, then features + ML, then neural from scratch, then pretrained fine-tuning, then LLM. Five variants of the same family count as ONE method.
2. **Difficulty**: calling a library < implementing it yourself < fine-tuning < designing a pipeline.
3. **Workload**: split evenly; each member does at least 1 method and 250 samples.

## 8. Experiment constraints
- Tune on dev, run test **once**. Fix the seed (42). With small data, report mean and standard deviation over several seeds.
- Every results table has a **trivial baseline** row (for example: answer = first sentence of the context / lead-k) and a **paper number** row. Bold the best number and state the metric and the split.
- LLM runs: temperature 0, cache every call result (JSON), bounded retries (never an infinite loop like the original code), report the share of invalid outputs, report cost and time per 1,000 samples, and record the model + version + call date + the full prompt (appendix). Few-shot examples come from train only. State clearly that the LLM may have already seen public data.
- API keys only through environment variables or `.env` (which is git-ignored). Never commit keys.

## 9. Data and ethics constraints
- Source: OpenStax (CC BY 4.0). Record the source and license, respect robots.txt and the terms of service, never scrape content behind a login, remove personal information.
- LLM-generated data must be labeled **synthetic** and must be checked by a human.
- Annotation: write a guideline (definitions of the 7 criteria from Table 12 of the paper, examples, hard cases, tie-break rules), pilot on 30 samples before real labeling, and double-annotate at least 20% of the samples to compute kappa.
- Every pipeline step logs the number of samples in and out (the numbers for 4.3). Deduplicate across members and against the original dataset.
- 4.3 must contain: a paper-versus-group comparison table (number of samples, label / criterion distribution in %, mean length, vocabulary, kappa, time / cost), distribution charts, a length histogram, characteristic n-grams, a table of representative examples and hard cases.

## 10. Deliverables and format
- **Phase 0/1 (upcoming, online, 5-10 minutes)**: input / output format of the paper's dataset; results and architecture of the paper's baselines; the data-collection plan. About 10 slides: (1) title / members, (2) motivation, (3) task card, (4) paper dataset, (5) metrics, (6-7) related works with at least 5 cited rows grouped by method family, (8) paper idea, (9-10) plan and assignment.
- **Task card** (required in phase 1 and at the end): problem name, input (type, length, language), output, 2-3 REAL examples from the dataset, main metric and why, the paper's baseline numbers.
- **Final**: slides on the course template (font size at least 24pt, every figure has a caption and source, last slide is the contribution table in %), a report (Introduction / Related / Method / Data / Experiments / Conclusion / Appendix: prompts + guideline + contributions), code with a README that reproduces at least 1 result within 15 minutes, the JSONL dataset plus its statistics.
- Target code layout: see section 14 (the paper's original code stays in its own folders so it can be cited).

## 11. Academic integrity
- Cite every paper, code base and dataset. State clearly where AI assistance was used.
- Never invent numbers and never adjust results to match the paper. Results that cannot be reproduced from the submitted code score 0.
- Git: each member commits their own part; weekly meeting with 5-line minutes; the contribution table in % must be agreed by the whole group.

---
# Team working rules

## 12. Language and writing
- **Everything in this repository is written in English**: code, comments, docstrings, documentation, commit messages, pull request titles and descriptions, branch names, issue text and file names. No Vietnamese in the repository.
- Personal notes that stay outside the repository may use any language.
- Keep text factual and short. Do not paste chat logs or AI output into documentation without reading and checking it.

## 13. Secrets and API keys
- Never commit an API key, token or password, in any file, including notebooks, logs and result files.
- Provide keys through environment variables (PowerShell: `$env:OPENAI_API_KEY="<key>"`; bash: `export OPENAI_API_KEY=<key>`) or a local `.env` file, which is git-ignored. `.env.example` lists the variable names only.
- Do **not** write a key into `Persona_models/.env.local`. The upstream repository already tracks that file, so `.gitignore` does not protect it.
- If a key is ever committed or shown on screen, **revoke and replace it immediately**. Deleting the file in a later commit does not remove it from git history.
- Do not paste keys, personal emails or private data into issues, PRs, chats with AI tools or screenshots.

## 14. Repository layout and what to commit
Upstream folders stay where they are and are not renamed or moved: `Persona_models/`, `metrics/`, `example_textbook_data/`, `generated_dataset/`, `images/`.

Folders added by the group:
| Folder | Content |
|---|---|
| `src/` | group source code (`split.py`, `evaluate.py`, `baselines/`, `llm/`, `collect/`, `annotate/`) |
| `data/` | `data/splits/` (train / dev / test), `data/group/` (the 1,000-sample JSONL) |
| `prompts/` | LLM prompts, versioned (`v1`, `v2`, ...) |
| `results/` | result tables, predictions, cost and time logs |
| `notebooks/` | exploratory analysis and plots |
| `docs/` | annotation guideline, meeting notes |

- **Commit:** source code, prompts, the final group dataset JSONL, split files, result tables, documentation.
- **Do not commit** (already in `.gitignore`): API keys and `.env`, raw downloaded OpenStax pages, model weights and checkpoints, LLM response caches, virtual environments, `__pycache__`, OS files such as `.DS_Store`.
- GitHub rejects files over 100 MB and warns above 50 MB. Do not commit anything near that size; share large files another way and document how to fetch them.
- Every script takes input and output paths as arguments. No hard-coded absolute paths and no usernames in paths.
- Group code must be reproducible: fixed seed 42, pinned versions in `requirements.txt`, and a README line showing how to run it.

## 15. Shared and personal files
- `.claude/` inside the repository is **shared by the whole group**: project rules, the plan and progress, and the open questions for the lecturer. Keep it accurate and in English.
- Personal notes, drafts and tool settings stay **outside** the repository, or in files matching `.claude/*.local.md` and `.claude/settings.local.json`, which are git-ignored.
- Progress and plan: each member edits only their own rows or sections, so that four people do not conflict on one file.
- Upstream code and data are CC BY-SA 4.0. Keep the attribution in `README.md` and make it clear which parts were written by the group.

## 16. Open decisions (update when answered)
| # | Decision | Current proposal | Status |
|---|---|---|---|
| 1 | What counts as "1 sample" for the 250 per member | 1 QA pair (about 42 dialogues x 6 pairs per member) | waiting for the lecturer |
| 2 | Group number `XX` used in sample ids | placeholder `gXX` | waiting for the lecturer |
| 3 | Dataset language | English, as in the paper | waiting for the lecturer |
| 4 | Value format of `labels` and `llm_labels` | one 0/1 value per criterion for each QA pair | to be agreed by the group |
| 5 | Which basic method families are accepted for a generation paper | reduce part 2 to the subtask `(S, h<t, q_t) -> a_t` | waiting for the lecturer |
