# CLAUDE.md: Book2Dial

> Group rules (language, git workflow, secrets, deliverables): see `.claude/rules/project-rules.md`. Read it before making changes.

## Overview
Book2Dial (ACL 2024 Findings; Wang, Macina, Daheim, Pal Chowdhury, Sachan; ETH LRE) is a framework that generates **synthetic teacher-student dialogues from textbooks** for developing educational chatbots. A student (LLM) asks questions about one textbook subsection and a teacher (LLM) answers based on the textbook text. It covers 4 domains: math, business, science and social science. License: CC BY-SA 4.0.

The repository contains **plain Python code only: no tests and no build system**. Scripts are run directly with `python`.

## Directory structure
```
book2dial/
├── README.md                     # Project description, data formats, how to run
├── requirements.txt              # openai==1.35.9 (data generation only)
├── example_textbook_data/        # Input textbooks (JSON)
│   ├── example.json              # one small sample (~19KB), for trying things out
│   ├── business_train_full.json  # ~1.2MB
│   ├── math_train_full.json      # ~1.3MB
│   ├── science_train_full.json   # ~2.3MB
│   └── social_train_full.json    # ~7.3MB
├── Persona_models/               # 3 dialogue generation scripts (prompting, OpenAI API)
│   ├── Persona_high_info_final.py
│   ├── Persona_medium_info_final.py
│   ├── Persona_low_info_final.py
│   └── .env.local                # empty file (the README says to create it for the key)
├── generated_dataset/            # Generated data (Persona high info), JSONL
│   ├── business_Persona_high_info.jsonl  (123 lines)
│   ├── math_Persona_high_info.jsonl      (142 lines)
│   ├── science_Persona_high_info.jsonl   (228 lines)
│   └── social_Persona_high_info.jsonl    (396 lines)   -> 889 dialogues in total
├── metrics/                      # Scripts that score dialogue quality
│   ├── requirements.txt          # transformers, bert_score, nltk, newsroom, sentence-transformers, scikit-learn, questeval
│   └── *.py                      # 9 metrics (see below)
└── images/evaluation.png         # Evaluation figure used in the README
```

## Data formats

### Input (textbook): `{"data": [ <subsection>, ... ]}`
Each element is one subsection:
- `title`: chapter / subsection name (for example `1-1-physics-definitions-and-applications`)
- `paragraphs`: list of `{context, id}`; **the code only uses `paragraphs[0]["context"]`** as the subsection text
- `section_title`: subsection heading
- `chapter_learning_objectives` (list of str), `chapter_summary` (str), `chapter_introduction` (str)
- `bold_terms` (list of str), `chapter_concept` (list of `{name, description}`)

### Raw output of the scripts (`generate_and_save_dialogs`)
Each JSONL line: `{"title", "context", "dialogs": [{"question", "answer"}, ...]}` (6 question-answer pairs per subsection by default, because `turns=12` and the loop runs `turns // 2` times).

### Released dataset (`generated_dataset/*.jsonl`)
Each line has `title`, `history` (list alternating question / answer), `qas` (the Q&A pairs) and `uid`. Note: this differs from the raw script output above (`dialogs`).

### Input of the metrics
Each JSONL line must contain `context` (str) and `dialogue` (list of str, alternating: even index = question, odd index = answer). This format **differs** from `history` in the released dataset and from `dialogs` in the script output, so a conversion step is needed before running the metrics.

## Data generation (Persona_models)
The three scripts are almost identical. They differ only in how much information the **student** (prompt 1) receives; the teacher prompt (prompt 2) is the same and always receives the full information, including the subsection text:

| Script | Information the student knows |
|---|---|
| `Persona_high_info_final.py` | Chapter title, subsection title, summary, bold terms, learning objectives, concepts, introduction |
| `Persona_medium_info_final.py` | Chapter title, subsection title, summary |
| `Persona_low_info_final.py` | Chapter title and subsection title only |

Main flow (per subsection): loop `turns//2` times -> `generate_question` (student prompt + `previous_conversation`) -> `generate_answer` (teacher prompt + subsection text + question) -> append to `previous_conversation` as `Student: ...\nTeacher: ...` -> `append_to_jsonl`.

Notable details:
- Uses `openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))`, default model `gpt-3.5-turbo` (variable `model_name`; can be changed to `gpt-4o` and so on).
- `generate_response0` retries **forever** (every 2 seconds) on any exception (a bare `except:`), so a wrong key or wrong model name loops endlessly.
- Supports **resume**: `check_current_progress` counts the lines of the output file and skips that many subsections.
- Input and output paths are **hard-coded** in `__main__`: input `./example_textbook_data/example.json`, output `test_science_{high|medium|low}_info.jsonl` (written to the current directory). Run from the repository root.
- The function `make_json_friendly` is defined but never used. In the low and medium scripts, prompt 2 takes parameters that it does not use.
- To use another API (for example OpenRouter), `base_url=` can be added to `OpenAI(...)`. The code does not yet support any configuration through the environment other than `OPENAI_API_KEY`. The empty `.env.local` is not loaded automatically (there is no `python-dotenv`), so environment variables must be exported manually.

## Metrics (`metrics/`)
All scripts share one CLI: `--file_path <in.jsonl> --output_path <out.csv> --device {cpu,gpu}`. They write a CSV with one score per line (one value per dialogue).

| File | What it measures |
|---|---|
| `Answerable.py` | 1 - share of unanswerable questions (DistilBERT SQuAD QA on the context; a question that does not end with `?` or an answer equal to `CANNOTANSWER` counts as unanswerable) |
| `QFactScore.py` | cos-sim(answer, QA-model answer) + cos-sim(question, answer) with `msmarco-distilbert-cos-v5` |
| `QuestEval.py` | QuestEval between the question (hypothesis) and the answer (source) |
| `Coverage.py` / `Density.py` | `newsroom` Fragments: how much of the dialogue is copied from the context (extractive coverage / density) |
| `BF1_qt_at.py` | BERTScore F1 (DeBERTa-large-MNLI) between question t and answer t |
| `BF1_qt_a_t-1.py` | BERTScore F1 between question t and the immediately preceding answer (t-1) |
| `BF1_qt_previous_a.py` | BERTScore F1 between question t and all previous answers (a<t) |
| `one_minus_overlap.py` | 1 - word overlap (lemmatized, as sets) between the current answer and the previous answers, which measures repetition |

Notes: `Answerable.py` and `QFactScore.py` both use `distilbert-base-cased-distilled-squad`. The first run downloads the HuggingFace models and `nltk wordnet`. `device` only takes effect in `QuestEval.py` (the other scripts compute a `device` variable but never pass it to the model).

## How to run
```bash
pip install -r requirements.txt            # openai==1.35.9
export OPENAI_API_KEY=<key>                # PowerShell: $env:OPENAI_API_KEY="<key>"
python Persona_models/Persona_high_info_final.py   # run from the repository root

pip install -r metrics/requirements.txt
python metrics/Answerable.py --file_path in.jsonl --output_path out.csv --device cpu
```
To use your own textbook: convert it to JSON in the input format above and edit the paths in `__main__` of the Persona script.

## Notes when editing
- The three Persona scripts duplicate almost all of their code. A change to the shared logic has to be made in all three (or refactored).
- There are no tests, lint or CI. Check changes by running on `example.json` (few subsections).
- The data files are large (`social_train_full.json` is ~7MB, the JSONL files are a few MB). Use offset / limit or `head -c` when reading, and do not read them whole.
- The original folder and variable names are kept (`example_textbook_data` holds the full training set, not only examples).
- Never commit an API key.
