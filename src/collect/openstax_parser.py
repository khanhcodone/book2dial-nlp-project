import argparse
import json
import re
from pathlib import Path
from typing import List, Optional
from bs4 import BeautifulSoup

EXERCISE_KEYWORDS = (
    "review questions",
    "critical thinking",
    "art connection",
    "exercise",
    "exercises",
    "practice test",
    "chapter review",
)

BOILERPLATE_PREFIXES = (
    "by the end of this section, you will be able to do the following",
    "in the example below, the scientific method is used",
    "decide if each of the following is an example",
)

OBJECTIVE_VERBS = (
    "identify ",
    "summarize ",
    "compare ",
    "describe ",
    "explain ",
    "discuss ",
    "distinguish ",
    "apply ",
    "evaluate ",
)

STOP_TERMS = {
    "if",
    "then",
    "or",
    "and",
    "the",
    "a",
    "an",
    "this",
    "that",
    "these",
    "those",
}

MOJIBAKE_MAP = {
    "\u00e2\u20ac\u2122": "'",
    "\u00e2\u20ac\u0153": '"',
    "\u00e2\u20ac\u009d": '"',
    "\u00e2\u20ac\u2014": "-",
    "\u00e2\u20ac\u2013": "-",
    "\u00c2": "",
}


def clean_text(text: str) -> str:
    cleaned = text or ""
    for bad, good in MOJIBAKE_MAP.items():
        cleaned = cleaned.replace(bad, good)
    return re.sub(r"\s+", " ", cleaned).strip()


def is_exercise_or_too_short(section_title: str, slug: str, context: str, min_chars: int) -> bool:
    haystack = f"{section_title.lower()} {slug.lower()}"
    if any(kw in haystack for kw in EXERCISE_KEYWORDS):
        return True
    if len(context) < min_chars:
        return True
    return False


def parse_section_html(
    html_text: str,
    slug: str,
    source_url: str,
    min_chars: int = 400,
) -> Optional[dict]:
    soup = BeautifulSoup(html_text, "html.parser")
    main_el = soup.find("main") or soup.body
    if not main_el:
        return None

    for tag in main_el.find_all(["nav", "footer", "script", "style", "aside"]):
        tag.decompose()

    heading_el = main_el.find(["h1", "h2"])
    section_title = clean_text(heading_el.get_text()) if heading_el else slug.replace("-", " ").title()

    para_texts: List[str] = []
    for p in main_el.find_all("p"):
        txt = clean_text(p.get_text())
        low = txt.lower()
        if len(txt) < 40:
            continue
        if any(low.startswith(bp) for bp in BOILERPLATE_PREFIXES):
            continue
        para_texts.append(txt)

    context = "\n\n".join(para_texts)
    if is_exercise_or_too_short(section_title, slug, context, min_chars=min_chars):
        return None

    bold_terms: List[str] = []
    seen_terms: set = set()
    for b_tag in main_el.find_all(["strong", "b", "em"]):
        term = clean_text(b_tag.get_text())
        low_term = term.lower()
        if len(term) <= 2 or len(term) > 80:
            continue
        if low_term in STOP_TERMS or low_term in seen_terms:
            continue
        seen_terms.add(low_term)
        bold_terms.append(term)

    learning_objectives: List[str] = []
    seen_obj: set = set()
    for li in main_el.find_all("li"):
        item_txt = clean_text(li.get_text())
        low_item = item_txt.lower()
        if not (15 <= len(item_txt) <= 240):
            continue
        if "therefore" in low_item or item_txt.endswith("?"):
            continue
        if any(low_item.startswith(v) for v in OBJECTIVE_VERBS) and low_item not in seen_obj:
            seen_obj.add(low_item)
            learning_objectives.append(item_txt)

    chapter_summary = para_texts[-1] if len(para_texts) > 1 else ""
    chapter_introduction = para_texts[0] if len(para_texts) > 1 else ""

    chapter_concept: List[dict] = []
    for dt, dd in zip(main_el.find_all("dt"), main_el.find_all("dd")):
        name = clean_text(dt.get_text())
        desc = clean_text(dd.get_text())
        if name and desc:
            chapter_concept.append({"name": name, "description": desc})

    return {
        "title": slug,
        "paragraphs": [
            {
                "context": context,
                "id": f"OS_{slug}",
            }
        ],
        "section_title": section_title,
        "chapter_learning_objectives": learning_objectives[:10],
        "chapter_summary": chapter_summary,
        "chapter_introduction": chapter_introduction,
        "bold_terms": bold_terms[:50],
        "chapter_concept": chapter_concept,
        "_meta": {
            "source_book": "OpenStax Biology 2e",
            "source_url": source_url,
            "license": "CC BY 4.0",
        },
    }


def parse_manifest(manifest_path: Path, out_json_path: Path, min_chars: int = 400) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("records", [])
    in_count = len(records)

    parsed_items: List[dict] = []
    for rec in records:
        html_path = Path(rec["html_file"])
        if not html_path.exists():
            continue
        item = parse_section_html(
            html_text=html_path.read_text(encoding="utf-8"),
            slug=rec["slug"],
            source_url=rec["url"],
            min_chars=min_chars,
        )
        if item is not None:
            parsed_items.append(item)

    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"data": parsed_items}
    out_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Parse stats: in={in_count}, out={len(parsed_items)} -> {out_json_path}")
    return {"in_count": in_count, "out_count": len(parsed_items)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse crawled OpenStax HTML into Book2Dial textbook JSON.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/raw_openstax/biology-2e/manifest.json"),
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("data/raw_openstax/biology_2e_parsed.json"),
    )
    parser.add_argument("--min-chars", type=int, default=400)
    args = parser.parse_args()
    parse_manifest(args.manifest, args.out_json, min_chars=args.min_chars)


if __name__ == "__main__":
    main()