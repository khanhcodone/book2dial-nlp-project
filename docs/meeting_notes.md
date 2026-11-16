# Meeting Notes

## Members
The letters A-D are role codes used in the plan and in sample ids. Note that C and D swap between the two phases.

| Letter | Phase 1 (slides) | Phase 2 (code and data) |
|---|---|---|
| A | Chuan | Chuan |
| B | Vu | Vu |
| C | Long | Khanh |
| D | Khanh | Long |

### Phase 2 responsibilities
| Letter | Name | Main responsibilities |
|---|---|---|
| A | Chuan | split / normalize / evaluate, methods M0 + M1, section 6 (reproduce Persona), README |
| B | Vu | crawler + parser + dedup, method M2, LLM zero-shot (L1), annotation guideline |
| C | Khanh | LLM wrapper, fix Persona scripts, method M3, LLM few-shot (L2), LLM labeling + kappa |
| D | Long | convert_for_metrics + metrics, method M4, section 5, statistics (4.3), slides |

## Phase 1 plan: report slides
Goal: split the reading and research so that the phase 1 presentation slides can be finished. Slide format required by the lecturer: about 10 slides.

| # | Slide | Content required by the lecturer | Owner | Preparation steps (in order) |
|---|---|---|---|---|
| 1 | Title | paper, group, members | A (builds the shared frame for the whole deck) | Write the paper name (Book2Dial, ACL 2024 Findings), group name, student ids and members. |
| 2 | Motivation | why the problem matters | A | Read section 1 of the paper; write 2-3 bullets: educational dialogue data is scarce (privacy, cost), so generate it from textbooks. |
| 3 | Task card | input, output, examples | B | 1) Read section 3 and Fig 1-2. 2) Redraw Fig 2. 3) Pick 2 real examples from `generated_dataset/`. 4) Write the input / output (small JSON format). |
| 4 | Paper dataset | key statistics | B | 1) Read section 3.2, Table 5, Appendix A / E / F. 2) Write a counting script: 4 books, 889 dialogues (142 / 123 / 228 / 396), 5,334 QA pairs, mean lengths, % of what / which / why / how questions. |
| 5 | Metric | which metrics and why | B | 1) Run 1-2 repo metrics (Answerable, Density) on a small sample. 2) Record the reliability of each metric (r = 0.81; 0.35; Uptake saturated). 3) Write the reason for choosing each metric. |
| 6-7 | Related works | table and critique | C | 1) Read sections 2 and 4, Appendix C. 2) Find and verify at least 6 works on ACL Anthology (QuAC, CoQA, MathDial, CIMA, SimSeek, Dialogue Inpainting): method family, data, results, limitations. 3) Build a table grouped by family, plus a critique and "How Book2Dial differs". |
| 8 | Group's paper | main idea (preliminary) | C (idea and architecture), D (baseline results) | C: summarize the architectures of SimSeek / Inpainting / Persona. D: take Tables 2, 3, 4 in condensed form and comment (21% factually wrong, 26% repetitive). |
| 9 | Plan (1/2) | methods | D | 1) Read sections 5 and 7, Appendix G. 2) Draft the method plan: M0-M4 and L1-L3 (parts 2-3). |
| 10 | Plan (2/2) | data, assignment | D | 1) Draft the data plan (6-step pipeline, labeling, 250 samples per member). 2) Assignment table and timeline; collect the questions for the lecturer. |

## How to use this file
- One entry per weekly meeting. Keep it short: the substance fits in about 5 lines.
- Add the entry on the day of the meeting and commit it the same day.
- Record decisions, not discussion. Never write keys, passwords or personal data here.
- Update the contribution log at every meeting. The final contribution table (in %) is built from it and must be agreed by all members.

## Meeting template (copy for each meeting)
```
### Meeting N - YYYY-MM-DD (week X)
- Attendees / absent:
- Done since last meeting (one line per member):
  - A:
  - B:
  - C:
  - D:
- Decisions (what was agreed, and who decided):
- Blockers / questions for the lecturer:
- Action items:
  | Owner | Task | Due |
  |---|---|---|
- Next meeting (date, time, place or link):
```

## Meetings
<!-- Add new meetings below, newest last. -->

### Meeting 1 - 2026-11-05 (kick-off)
- Attendees / absent: all members present.
- Done since last meeting: not applicable.
- Decisions: purpose of the meeting is to split the reading and research so that the phase 1 report slides can be finished. Phase 1 roles assigned (see the Members table and the Phase 1 plan above).
- Blockers / questions for the lecturer: none recorded.
- Action items: each member prepares their slides following the Phase 1 plan.
- Next meeting: 2026-11-13, slide review.

### Meeting 2 - 2026-11-13 (slide review)
- Attendees / absent: all members present.
- Done since last meeting: slide content is finished (all members).
- Decisions: reviewed the slides together. The content part is done, so the next step is slide design.
- Blockers / questions for the lecturer: none recorded.
- Action items: design the slides.
- Next meeting: 2026-11-16.

### Meeting 3 - 2026-11-16 (scheduled, not held yet)
- Attendees / absent:
- Done since last meeting:
- Decisions:
- Blockers / questions for the lecturer:
- Action items:
- Next meeting:

## Contribution log (running)
| Date | Member | What was done | Evidence (PR / commit / file) |
|---|---|---|---|
