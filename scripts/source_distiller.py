#!/usr/bin/env python3
"""
Deterministic source distillation helper.

Commands:
  index  <path> --out index.json
  search --index index.json --query "..." --top-k 8
  quote  --index index.json --cite S1:L10-L20
  audit  --index index.json --answer answer.md

No LLM calls. The point is to create compact, verifiable evidence packs with
source ids and line/page anchors that any agent can cite and re-check.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".yaml", ".yml",
    ".xml", ".html", ".htm", ".py", ".js", ".ts", ".tsx", ".jsx", ".css",
    ".java", ".go", ".rs", ".rb", ".php", ".c", ".cpp", ".h", ".hpp",
}
SUPPORTED_EXTS = TEXT_EXTS | {".pdf", ".docx"}
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "in", "is", "it", "its", "of", "on", "or", "that", "the", "to",
    "was", "were", "with", "this", "these", "those", "we", "you", "your",
    "ve", "veya", "ile", "icin", "için", "bir", "bu", "şu", "de", "da",
    "mi", "mu", "ne", "olan", "olarak",
}


@dataclass
class ExtractedSource:
    path: str
    kind: str
    lines: list[str]
    loc_prefix: str


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9_'-]{2,}", text.lower())
    return [w for w in words if w not in STOPWORDS]


def strip_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t]+", " ", text)


def read_text_file(path: Path) -> list[str]:
    raw = path.read_bytes()
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
    if path.suffix.lower() in {".html", ".htm"}:
        text = strip_html(text)
    return text.splitlines()


def read_docx(path: Path) -> list[str]:
    lines: list[str] = []
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    for para in root.findall(".//w:p", ns):
        texts = [t.text or "" for t in para.findall(".//w:t", ns)]
        line = "".join(texts).strip()
        if line:
            lines.append(line)
    return lines


def read_pdf(path: Path) -> tuple[list[str], list[int]]:
    if shutil.which("pdftotext"):
        proc = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            text=True,
            capture_output=True,
            check=True,
        )
        pages = proc.stdout.split("\f")
    else:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF support requires `pdftotext` on PATH or Python package `pypdf`") from exc
        reader = PdfReader(str(path))
        pages = [(page.extract_text() or "") for page in reader.pages]
    lines: list[str] = []
    page_for_line: list[int] = []
    for page_no, page in enumerate(pages, start=1):
        for line in page.splitlines():
            lines.append(line)
            page_for_line.append(page_no)
    return lines, page_for_line


def extract_source(path: Path) -> ExtractedSource:
    ext = path.suffix.lower()
    if ext == ".pdf":
        lines, page_for_line = read_pdf(path)
        # Prefix page into each line so quoted excerpts remain self-contained.
        page_counts: dict[int, int] = defaultdict(int)
        numbered = []
        for line, page in zip(lines, page_for_line):
            page_counts[page] += 1
            numbered.append(f"[p{page}:L{page_counts[page]}] {line}")
        return ExtractedSource(str(path), "pdf", numbered, "p")
    if ext == ".docx":
        return ExtractedSource(str(path), "docx", read_docx(path), "L")
    return ExtractedSource(str(path), ext.lstrip(".") or "text", read_text_file(path), "L")


def iter_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    ignored = {".git", "node_modules", ".next", "dist", "build", "__pycache__"}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in ignored for part in path.parts):
            continue
        if path.suffix.lower() in SUPPORTED_EXTS:
            yield path


def make_chunks(source_id: str, source: ExtractedSource, chunk_lines: int, overlap: int):
    lines = source.lines
    i = 0
    while i < len(lines):
        chunk = lines[i : i + chunk_lines]
        text = "\n".join(chunk).strip()
        if text:
            yield {
                "source_id": source_id,
                "start_line": i + 1,
                "end_line": i + len(chunk),
                "text": text,
                "terms": Counter(tokenize(text)),
            }
        if i + chunk_lines >= len(lines):
            break
        i += max(1, chunk_lines - overlap)


def build_index(args) -> int:
    root = Path(args.path).expanduser().resolve()
    files = list(iter_files(root))
    sources = []
    chunks = []
    for idx, path in enumerate(files, start=1):
        sid = f"S{idx}"
        try:
            extracted = extract_source(path)
        except Exception as exc:
            print(f"skip {path}: {exc}", file=sys.stderr)
            continue
        rel = str(path.relative_to(root)) if root.is_dir() else path.name
        sources.append({
            "id": sid,
            "path": str(path),
            "display": rel,
            "kind": extracted.kind,
            "line_count": len(extracted.lines),
        })
        chunks.extend(make_chunks(sid, extracted, args.chunk_lines, args.overlap))

    serial_chunks = []
    doc_freq = Counter()
    for chunk in chunks:
        for term in chunk["terms"]:
            doc_freq[term] += 1
    for cid, chunk in enumerate(chunks, start=1):
        serial_chunks.append({
            "id": f"C{cid}",
            "source_id": chunk["source_id"],
            "start_line": chunk["start_line"],
            "end_line": chunk["end_line"],
            "text": chunk["text"],
            "terms": dict(chunk["terms"]),
        })

    data = {
        "version": 1,
        "root": str(root),
        "sources": sources,
        "chunks": serial_chunks,
        "doc_freq": dict(doc_freq),
        "chunk_count": len(serial_chunks),
    }
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"indexed {len(sources)} sources, {len(serial_chunks)} chunks -> {out}")
    return 0


def load_index(path: str):
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def citation(chunk) -> str:
    return f"{chunk['source_id']}:L{chunk['start_line']}-L{chunk['end_line']}"


def score_chunks(index, query: str):
    q_terms = Counter(tokenize(query))
    if not q_terms:
        return []
    n = max(1, index["chunk_count"])
    scored = []
    for chunk in index["chunks"]:
        terms = chunk.get("terms", {})
        score = 0.0
        for term, qtf in q_terms.items():
            tf = terms.get(term, 0)
            if not tf:
                continue
            df = index.get("doc_freq", {}).get(term, 1)
            idf = math.log((n + 1) / (df + 0.5)) + 1
            score += (1 + math.log(tf)) * idf * qtf
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def command_search(args) -> int:
    index = load_index(args.index)
    source_lookup = {s["id"]: s for s in index["sources"]}
    hits = score_chunks(index, args.query)[: args.top_k]
    if args.json:
        print(json.dumps([
            {
                "score": round(score, 4),
                "citation": citation(chunk),
                "source": source_lookup[chunk["source_id"]]["display"],
                "excerpt": chunk["text"][: args.max_chars],
            }
            for score, chunk in hits
        ], ensure_ascii=False, indent=2))
        return 0
    for rank, (score, chunk) in enumerate(hits, start=1):
        src = source_lookup[chunk["source_id"]]
        excerpt = chunk["text"]
        if len(excerpt) > args.max_chars:
            excerpt = excerpt[: args.max_chars].rstrip() + "\n..."
        print(f"\n[{rank}] {citation(chunk)} score={score:.3f} source={src['display']}")
        print(excerpt)
    return 0


def parse_cite(cite: str):
    m = re.fullmatch(r"(S\d+):L(\d+)-L(\d+)", cite.strip())
    if not m:
        raise ValueError("citation must look like S1:L10-L20")
    return m.group(1), int(m.group(2)), int(m.group(3))


def command_quote(args) -> int:
    index = load_index(args.index)
    sid, start, end = parse_cite(args.cite)
    source = next((s for s in index["sources"] if s["id"] == sid), None)
    if not source:
        raise SystemExit(f"unknown source id: {sid}")
    extracted = extract_source(Path(source["path"]))
    lines = extracted.lines[start - 1 : end]
    print(f"{args.cite} {source['display']}")
    for n, line in enumerate(lines, start=start):
        print(f"{n}: {line}")
    return 0


def command_audit(args) -> int:
    index = load_index(args.index)
    text = Path(args.answer).expanduser().read_text(encoding="utf-8")
    source_ids = {s["id"] for s in index["sources"]}
    source_lookup = {s["id"]: s for s in index["sources"]}
    cites = re.findall(r"S\d+:L\d+-L\d+|S\d+", text)
    bad = []
    for c in cites:
        sid = c.split(":")[0]
        if sid not in source_ids:
            bad.append((c, "unknown source"))
            continue
        if ":L" in c:
            try:
                _, start, end = parse_cite(c)
            except ValueError as exc:
                bad.append((c, str(exc)))
                continue
            line_count = next(s["line_count"] for s in index["sources"] if s["id"] == sid)
            if start < 1 or end > line_count or start > end:
                bad.append((c, f"line range outside 1-{line_count}"))

    uncited_blocks = []
    numeric_mismatches = []
    for block in re.split(r"\n\s*\n", text):
        stripped = block.strip()
        if not stripped or stripped.startswith("|") or stripped.startswith("#"):
            continue
        if len(stripped) > args.min_block_chars and not re.search(r"S\d+", stripped):
            uncited_blocks.append(stripped[:160].replace("\n", " "))
            continue
        if args.strict_numbers and re.search(r"S\d+:L\d+-L\d+", stripped):
            block_numbers = set(extract_numbers(re.sub(r"S\d+:L\d+-L\d+|S\d+", "", stripped)))
            if not block_numbers:
                continue
            cited_text = []
            for cite in re.findall(r"S\d+:L\d+-L\d+", stripped):
                sid, start, end = parse_cite(cite)
                source = source_lookup.get(sid)
                if not source:
                    continue
                extracted = extract_source(Path(source["path"]))
                cited_text.extend(extracted.lines[start - 1 : end])
            cited_numbers = set(extract_numbers("\n".join(cited_text)))
            missing_numbers = sorted(block_numbers - cited_numbers)
            if missing_numbers:
                numeric_mismatches.append((stripped[:160].replace("\n", " "), missing_numbers))

    print(f"citations_found: {len(cites)}")
    print(f"bad_citations: {len(bad)}")
    for c, reason in bad:
        print(f"- {c}: {reason}")
    print(f"possibly_uncited_blocks: {len(uncited_blocks)}")
    for block in uncited_blocks[: args.max_uncited]:
        print(f"- {block}")
    print(f"numeric_mismatches: {len(numeric_mismatches)}")
    for block, nums in numeric_mismatches[: args.max_uncited]:
        print(f"- missing numbers {nums}: {block}")
    return 1 if bad or uncited_blocks or numeric_mismatches else 0


def extract_numbers(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?(?:\s?(?:MB|GB|KB|days?|months?|years?|%))?", text, flags=re.I)


def main() -> int:
    parser = argparse.ArgumentParser(description="Source Distiller CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("index")
    p.add_argument("path")
    p.add_argument("--out", default=".source-distiller/index.json")
    p.add_argument("--chunk-lines", type=int, default=40)
    p.add_argument("--overlap", type=int, default=5)
    p.set_defaults(func=build_index)

    p = sub.add_parser("search")
    p.add_argument("--index", required=True)
    p.add_argument("--query", required=True)
    p.add_argument("--top-k", type=int, default=8)
    p.add_argument("--max-chars", type=int, default=1200)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_search)

    p = sub.add_parser("quote")
    p.add_argument("--index", required=True)
    p.add_argument("--cite", required=True)
    p.set_defaults(func=command_quote)

    p = sub.add_parser("audit")
    p.add_argument("--index", required=True)
    p.add_argument("--answer", required=True)
    p.add_argument("--min-block-chars", type=int, default=120)
    p.add_argument("--max-uncited", type=int, default=10)
    p.add_argument("--strict-numbers", action=argparse.BooleanOptionalAction, default=True)
    p.set_defaults(func=command_audit)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
