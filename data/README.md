# data/

| Folder | Content | Committed? |
|---|---|---|
| `splits/` | `train.jsonl`, `dev.jsonl`, `test.jsonl` (split by dialogue, seed 42) | yes |
| `group/` | the group dataset, 250 samples per member, JSONL schema in `.claude/rules/project-rules.md` section 2 | yes |
| `raw_openstax/` | raw pages downloaded from OpenStax | no (git-ignored, fetch again with the crawler) |

The paper's own data stays in `example_textbook_data/` and `generated_dataset/`.
