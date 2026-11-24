"""Persona prompts of Book2Dial, copied verbatim from the paper's code.

Source: ``Persona_models/Persona_{high,medium,low}_info_final.py`` (Wang et al.,
ACL 2024 Findings, https://github.com/eth-lre/book2dial, CC BY-SA 4.0).
The prompt text is unchanged; only the code around it was restructured so that
one module serves all three info levels. The three original files differ only in
the student prompt:

    high   : section title, subsection title, summary, bold terms,
             learning objectives, concepts, introduction
    medium : section title, subsection title, summary
    low    : section title, subsection title

The teacher prompt is identical in the three files.
``python -m src.collect.generate_dialogs --check-prompts`` compares these
functions with the original ones.
"""
from __future__ import annotations

PROMPT_VERSION = "persona_v1"
INFO_LEVELS = ("high", "medium", "low")


def section_fields(section: dict) -> dict:
    """Extract the prompt fields from one textbook subsection, as the original code does."""
    return {
        "chapter_title": section["title"],
        "section_title": section["section_title"],
        "context": section["paragraphs"][0]["context"],
        "chapter_summary": section["chapter_summary"],
        "bold_terms": ", ".join(term.strip() for term in section["bold_terms"]),
        "learning_objectives": ", ".join(
            objective.strip() for objective in section["chapter_learning_objectives"]
        ),
        "concepts": ", ".join(concept["name"].strip() for concept in section["chapter_concept"]),
        "introduction": section["chapter_introduction"],
    }


def format_history(pairs: list[tuple[str, str]]) -> str:
    """Build ``previous_conversation`` exactly like the original loop."""
    return "".join(f"\nStudent: {q}\nTeacher: {a}" for q, a in pairs)


def student_prompt(f: dict, previous_conversation: str, info_level: str = "high") -> str:
    """Prompt 1 (student). ``f`` comes from :func:`section_fields`."""
    if info_level not in INFO_LEVELS:
        raise ValueError(f"info_level must be one of {INFO_LEVELS}, got {info_level!r}")
    info = (
        f"1. **Section Title:** {f['chapter_title']}\n"
        f"2. **Subsection Title:** {f['section_title']}\n"
    )
    if info_level in ("high", "medium"):
        info += f"3. **Section Summary:** {f['chapter_summary']}\n"
    if info_level == "high":
        info += (
            f"4. **Bold Terms in Section:** {f['bold_terms']}\n"
            f"5. **Learning Objectives:** {f['learning_objectives']}\n"
            f"6. **Concepts in Section:** {f['concepts']}\n"
            f"7. **Section Introduction:** {f['introduction']}\n\n"
        )
    return (
        "Task: You are a student preparing to ask questions about a textbook subsection to a teacher. "
        "Your goal is to uncover the key information from this subsection. Based on the teacher's responses, "
        "you'll further inquire to get a comprehensive understanding. Make sure to ask specific questions about "
        "the subsection's content and avoid repeating queries from prior discussions.\n\n"
        "Information Provided:\n"
        f"{info}"
        "Previous Conversation:\n"
        f"{previous_conversation}\n\n"
        "*Note:* Frame your questions considering the information above and ensure they're relevant to the content. Do not ask question about information you already have. Only ask one question at a time.\n\n"
        "Expected Output: Please phrase your question as a string."
    )


def teacher_prompt(f: dict, previous_conversation: str, question: str) -> str:
    """Prompt 2 (teacher). Always sees the full subsection text and formatting."""
    return (
        "Task: You are a teacher preparing to answer a student's question about a subsection of a textbook. "
        f"The student's question is: {question}. Provide a concise, specific response, ensuring it's not a summary and "
        "distinct from any previous answers you've given.\n\n"
        "Information Provided:\n"
        f"1. **Section Title:** {f['chapter_title']}\n"
        f"2. **Subsection Title:** {f['section_title']}\n"
        f"3. **Subsection Content:** {f['context']}\n"
        f"4. **Section Summary:** {f['chapter_summary']}\n"
        f"5. **Bold Terms in Section:** {f['bold_terms']}\n"
        f"6. **Learning Objectives:** {f['learning_objectives']}\n"
        f"7. **Concepts in Section:** {f['concepts']}\n"
        f"8. **Section Introduction:** {f['introduction']}\n\n"
        "Previous Conversation:\n"
        f"{previous_conversation}\n\n"
        "*Note:* When crafting your response, consider all the information above. Be sure your answer directly "
        "addresses the student's question and is not a repetition of prior information.\n\n"
        "Expected Output: Please phrase your answer as a string."
    )
