import argparse
import json
import re
import time
from pathlib import Path
from typing import List
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
import requests

DEFAULT_HEADERS = {
    "User-Agent": "CSC15011-Book2Dial-Collector/1.0 (Academic research; university project)"
}

DEFAULT_BIOLOGY_2E_SLUGS = [
    # Chapter 1–3
    "1-1-the-science-of-biology",
    "1-2-themes-and-concepts-of-biology",
    "2-1-atoms-isotopes-ions-and-molecules-the-building-blocks",
    "2-2-water",
    "2-3-carbon",
    "3-1-synthesis-of-biological-macromolecules",
    "3-2-carbohydrates",
    "3-3-lipids",
    "3-4-proteins",
    "3-5-nucleic-acids",
    # Chapter 4–6
    "4-1-studying-cells",
    "4-2-prokaryotic-cells",
    "4-3-eukaryotic-cells",
    "4-4-the-endomembrane-system-and-proteins",
    "4-5-the-cytoskeleton",
    "4-6-connections-between-cells-and-cellular-activities",
    "5-1-components-and-structure",
    "5-2-passive-transport",
    "5-3-active-transport",
    "5-4-bulk-transport",
    "6-1-energy-and-metabolism",
    "6-2-potential-kinetic-free-and-activation-energy",
    "6-3-the-laws-of-thermodynamics",
    "6-4-atp-adenosine-triphosphate",
    "6-5-enzymes",
    # Chapter 7–8
    "7-1-energy-in-living-systems",
    "7-2-glycolysis",
    "7-3-oxidation-of-pyruvate-and-the-citric-acid-cycle",
    "7-4-oxidative-phosphorylation",
    "7-5-metabolism-without-oxygen",
    "7-7-regulation-of-cellular-respiration",
    "8-1-overview-of-photosynthesis",
    "8-2-the-light-dependent-reactions-of-photosynthesis",
    "8-3-using-light-energy-to-make-organic-molecules",
    # Chapter 15–21 (verified 200)
    "15-1-the-genetic-code",
    "16-1-regulation-of-gene-expression",
    "16-2-prokaryotic-gene-regulation",
    "18-1-understanding-evolution",
    "18-2-formation-of-new-species",
    "19-1-population-evolution",
    "19-2-population-genetics",
    "20-1-organizing-life-on-earth",
    "20-2-determining-evolutionary-relationships",
    "21-1-viral-evolution-morphology-and-classification",
]


def can_fetch(base_url: str, target_url: str, user_agent: str) -> bool:
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        return rp.can_fetch(user_agent, target_url)
    except Exception:
        return True


def extract_pages_root(toc_url: str) -> str:
    parsed = urlparse(toc_url)
    match = re.match(r"^(/books/[^/]+/pages/)", parsed.path)
    if match:
        return f"{parsed.scheme}://{parsed.netloc}{match.group(1)}"
    return toc_url.rstrip("/") + "/"


def discover_section_urls(book_toc_url: str, max_sections: int = 55) -> List[str]:
    pages_root = extract_pages_root(book_toc_url)
    urls: List[str] = []
    seen: set = set()

    try:
        resp = requests.get(book_toc_url, headers=DEFAULT_HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            full_url = urljoin(book_toc_url, href).split("#")[0].rstrip("/")
            if not full_url.startswith(pages_root.rstrip("/") + "/"):
                continue
            slug = full_url.split("/")[-1]
            if re.match(r"^\d+-\d+", slug) and full_url not in seen:
                seen.add(full_url)
                urls.append(full_url)
                if len(urls) >= max_sections:
                    return urls
    except Exception as exc:
        print(f"[WARN] TOC discovery fallback triggered: {exc}")

    for slug in DEFAULT_BIOLOGY_2E_SLUGS:
        fallback_url = f"{pages_root.rstrip('/')}/{slug}"
        if fallback_url not in seen:
            seen.add(fallback_url)
            urls.append(fallback_url)
            if len(urls) >= max_sections:
                break

    return urls


def crawl_openstax(
    toc_url: str,
    out_dir: Path,
    max_sections: int = 55,
    delay_sec: float = 1.0,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    ua = DEFAULT_HEADERS["User-Agent"]
    candidate_urls = discover_section_urls(toc_url, max_sections=max_sections)

    in_count = len(candidate_urls)
    saved_records: List[dict] = []

    for idx, url in enumerate(candidate_urls, start=1):
        if not can_fetch(toc_url, url, ua):
            print(f"[SKIP robots.txt] {url}")
            continue

        slug = url.rstrip("/").split("/")[-1]
        html_path = out_dir / f"{slug}.html"

        if html_path.exists():
            html_text = html_path.read_text(encoding="utf-8")
        else:
            try:
                resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
                resp.raise_for_status()
            except requests.RequestException as exc:
                print(f"[WARN SKIP] {url} -> {exc}")
                continue
            soup_raw = BeautifulSoup(resp.content, "html.parser")
            html_text = soup_raw.prettify()
            html_path.write_text(html_text, encoding="utf-8")
            time.sleep(delay_sec)

        saved_records.append(
            {
                "index": idx,
                "slug": slug,
                "url": url,
                "html_file": str(html_path),
            }
        )

    manifest = {
        "toc_url": toc_url,
        "license": "CC BY 4.0",
        "in_count": in_count,
        "out_count": len(saved_records),
        "records": saved_records,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Crawl stats: in={in_count}, out={len(saved_records)} -> {manifest_path}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl OpenStax textbook sections.")
    parser.add_argument(
        "--toc-url",
        type=str,
        default="https://openstax.org/books/biology-2e/pages/1-introduction",
        help="OpenStax book table-of-contents / start page URL",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/raw_openstax/biology-2e"),
        help="Directory to store raw HTML files",
    )
    parser.add_argument("--max-sections", type=int, default=55)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    crawl_openstax(
        toc_url=args.toc_url,
        out_dir=args.out_dir,
        max_sections=args.max_sections,
        delay_sec=args.delay,
    )


if __name__ == "__main__":
    main()