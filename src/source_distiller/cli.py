#!/usr/bin/env python3
"""
Source Distiller CLI.

Deterministic, zero-LLM citation engine for multi-document research.
Index any mix of PDFs, docs, and code; search with line-level citations;
verify every quote; audit drafts for fake references; detect cross-source
conflicts — all from your terminal.

Commands:
  index      Build a deterministic source index
  search     Retrieve top-k evidence with citations
  quote      Re-open a cited span for verification
  audit      Check a draft for fake/invalid citations
  conflicts  Detect cross-document disagreements
  report     Generate a full evidence report
  chat       Interactive REPL for search + quote
  stats      Quick index overview
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
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


__version__ = "0.1.0"

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
    "not", "no", "but", "can", "do", "does", "did", "will", "would", "should",
    "ve", "veya", "ile", "icin", "için", "bir", "bu", "şu", "de", "da",
    "mi", "mu", "ne", "olan", "olarak",
}

# Signals that two chunks may disagree.
NEGATION_SIGNALS = {
    "not", "no", "never", "without", "instead", "however", "but", "whereas",
    "unlike", "contrary", "conflict", "disagree", "incorrect", "wrong",
    "rather", "although", "despite", "challenge", "limitation", "fail",
    "insufficient", "lack", "gap", "problem", "issue", "risk",
}


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

@dataclass
class ExtractedSource:
    path: str
    kind: str
    lines: list[str]
    loc_prefix: str


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9_'-]{2,}", text.lower())
    return [w for w in words if w not in STOPWORDS]


def bigrams(tokens: list[str]) -> list[str]:
    return [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]


def tokenize_with_bigrams(text: str) -> list[str]:
    unigrams = tokenize(text)
    return unigrams + bigrams(unigrams)


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
            raise RuntimeError(
                "PDF support requires `pdftotext` on PATH or `pip install source-distiller[pdf]`"
            ) from exc
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


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def make_chunks(source_id: str, source: ExtractedSource, chunk_lines: int, overlap: int):
    lines = source.lines
    i = 0
    while i < len(lines):
        chunk = lines[i : i + chunk_lines]
        text = "\n".join(chunk).strip()
        if text:
            uni = tokenize(text)
            terms = Counter(uni + bigrams(uni))
            yield {
                "source_id": source_id,
                "start_line": i + 1,
                "end_line": i + len(chunk),
                "text": text,
                "terms": terms,
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
    doc_freq: Counter = Counter()
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
        "version": 2,
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


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def load_index(path: str):
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def citation(chunk) -> str:
    return f"{chunk['source_id']}:L{chunk['start_line']}-L{chunk['end_line']}"


def score_chunks(index, query: str):
    q_tokens = tokenize(query)
    q_terms = Counter(q_tokens + bigrams(q_tokens))
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


# ---------------------------------------------------------------------------
# Quote
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def extract_numbers(text: str) -> list[str]:
    return re.findall(
        r"(?<![A-Za-z])\d+(?:\.\d+)?(?:\s?(?:MB|GB|KB|days?|months?|years?|%))?",
        text, flags=re.I,
    )


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
            for cite_match in re.findall(r"S\d+:L\d+-L\d+", stripped):
                sid, start, end = parse_cite(cite_match)
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


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------

def _chunk_topic_terms(chunk: dict) -> set[str]:
    """Content-bearing terms (unigrams only, no bigrams) for topic similarity."""
    return {t for t in chunk.get("terms", {}) if "_" not in t}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _tfidf_cosine(terms_a: dict, terms_b: dict, doc_freq: dict, n: int) -> float:
    """TF-IDF weighted cosine similarity — catches topical overlap even with low Jaccard."""
    shared = set(terms_a) & set(terms_b)
    shared = {t for t in shared if "_" not in t}  # unigrams only
    if not shared:
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    all_terms = set(terms_a) | set(terms_b)
    for t in all_terms:
        if "_" in t:
            continue
        df = doc_freq.get(t, 1)
        idf = math.log((n + 1) / (df + 0.5)) + 1
        wa = terms_a.get(t, 0) * idf
        wb = terms_b.get(t, 0) * idf
        dot += wa * wb
        norm_a += wa * wa
        norm_b += wb * wb
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def _negation_score(text: str) -> int:
    words = set(text.lower().split())
    return len(words & NEGATION_SIGNALS)


def _is_year(val: str) -> bool:
    """Check if a numeric value looks like a year (1900-2099)."""
    digits = re.sub(r"[^\d]", "", val)
    return digits.isdigit() and 1900 <= int(digits) <= 2099


def _is_noise_number(val: str) -> bool:
    """Filter out list numbers (1-9 without units) and years."""
    clean = val.strip().rstrip(".")
    if _is_year(clean):
        return True
    # Plain small integers without units (likely list items)
    if re.fullmatch(r"[1-9]", clean):
        return True
    return False


def _extract_numeric_context(text: str) -> dict[str, set[str]]:
    """Extract numbers with sentence-level context words for conflict detection.

    Splits text into sentences, then associates each number with the key
    topic words in its sentence. This gives precise context without the
    noise of a wide character window.
    """
    nums: dict[str, set[str]] = defaultdict(set)
    num_pat = re.compile(r"\d+(?:\.\d+)?(?:\s?(?:MB|GB|KB|days?|months?|years?|%))?", re.I)
    # Split into sentences (period/newline/bullet boundaries)
    sentences = re.split(r"[.\n•\-]+", text)
    for sent in sentences:
        numbers_in_sent = []
        for m in num_pat.finditer(sent.lower()):
            val = m.group(0).strip()
            if not _is_noise_number(val):
                numbers_in_sent.append(val)
        if not numbers_in_sent:
            continue
        # Get topic words from this sentence
        words = re.findall(r"[a-z]{4,}", sent.lower())
        topic_words = [w for w in words if w not in STOPWORDS]
        for tw in topic_words:
            for nv in numbers_in_sent:
                nums[tw].add(nv)
    return nums


def _number_conflicts(text_a: str, text_b: str) -> list[tuple[str, str]]:
    """Find numbers attached to the same context word but with different values."""
    nums_a = _extract_numeric_context(text_a)
    nums_b = _extract_numeric_context(text_b)
    conflicts = []
    for key in nums_a.keys() & nums_b.keys():
        diff = nums_a[key] ^ nums_b[key]
        if diff and nums_a[key] != nums_b[key]:
            conflicts.append((key, f"{nums_a[key]} vs {nums_b[key]}"))
    return conflicts


def _percentage_conflicts(text_a: str, text_b: str) -> list[tuple[str, str]]:
    """Detect conflicting percentages near shared topic words."""
    pct_pat = re.compile(r"(\d+(?:\.\d+)?)\s?%")
    pcts_a = set(pct_pat.findall(text_a))
    pcts_b = set(pct_pat.findall(text_b))
    if not pcts_a or not pcts_b:
        return []
    # Only flag when there are actually different percentage values
    diff = pcts_a ^ pcts_b
    if not diff:
        return []
    # Check that both chunks share at least one topic word near a percentage
    # to avoid false positives between unrelated chunks
    words_a = set(re.findall(r"[a-z]{4,}", text_a.lower())) - STOPWORDS
    words_b = set(re.findall(r"[a-z]{4,}", text_b.lower())) - STOPWORDS
    shared_topics = words_a & words_b
    if len(shared_topics) >= 3:
        return [("percentages", f"{pcts_a} vs {pcts_b}")]
    return []


def find_conflicts(index: dict, *, min_similarity: float = 0.15, top_n: int = 20) -> list[dict]:
    """Find chunk pairs from different sources that are topically similar but may disagree."""
    chunks = index["chunks"]
    source_lookup = {s["id"]: s for s in index["sources"]}
    doc_freq = index.get("doc_freq", {})
    n_chunks = max(1, index.get("chunk_count", len(chunks)))
    topic_cache = {}
    for c in chunks:
        topic_cache[c["id"]] = _chunk_topic_terms(c)

    candidates = []
    for i, ca in enumerate(chunks):
        for j in range(i + 1, len(chunks)):
            cb = chunks[j]
            if ca["source_id"] == cb["source_id"]:
                continue

            jacc = _jaccard(topic_cache[ca["id"]], topic_cache[cb["id"]])
            tfidf = _tfidf_cosine(
                ca.get("terms", {}), cb.get("terms", {}), doc_freq, n_chunks
            )
            # Use the better of the two similarity measures
            sim = max(jacc, tfidf)

            neg = _negation_score(ca["text"]) + _negation_score(cb["text"])
            num_conflicts = _number_conflicts(ca["text"], cb["text"])
            pct_conflicts = _percentage_conflicts(ca["text"], cb["text"])

            # Merge percentage conflicts into num_conflicts for display
            all_num = num_conflicts + [p for p in pct_conflicts if p not in num_conflicts]

            # Lower threshold when numeric conflicts exist — numbers don't lie
            effective_min_sim = min_similarity
            if all_num:
                effective_min_sim = min(0.05, min_similarity)

            if sim < effective_min_sim:
                continue

            conflict_score = (
                sim * 0.3
                + min(neg, 5) * 0.1
                + len(num_conflicts) * 0.3
                + len(pct_conflicts) * 0.25
            )
            if conflict_score > 0.05:
                candidates.append({
                    "score": round(conflict_score, 3),
                    "similarity": round(sim, 3),
                    "negation_signals": neg,
                    "numeric_conflicts": all_num,
                    "chunk_a": citation(ca),
                    "source_a": source_lookup[ca["source_id"]]["display"],
                    "chunk_b": citation(cb),
                    "source_b": source_lookup[cb["source_id"]]["display"],
                    "excerpt_a": ca["text"][:300],
                    "excerpt_b": cb["text"][:300],
                })
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_n]


def command_conflicts(args) -> int:
    index = load_index(args.index)
    conflicts = find_conflicts(index, min_similarity=args.min_similarity, top_n=args.top_n)
    if args.json:
        print(json.dumps(conflicts, ensure_ascii=False, indent=2))
        return 0
    if not conflicts:
        print("No cross-source conflicts detected.")
        return 0
    print(f"Found {len(conflicts)} potential cross-source conflicts:\n")
    for i, c in enumerate(conflicts, 1):
        print(f"--- Conflict #{i} (score={c['score']}) ---")
        print(f"  {c['chunk_a']} [{c['source_a']}]")
        print(f"  vs")
        print(f"  {c['chunk_b']} [{c['source_b']}]")
        print(f"  similarity={c['similarity']}  negation_signals={c['negation_signals']}")
        if c["numeric_conflicts"]:
            for key, vals in c["numeric_conflicts"]:
                print(f"  numeric: {key} -> {vals}")
        print(f"  A: {c['excerpt_a'][:120]}...")
        print(f"  B: {c['excerpt_b'][:120]}...")
        print()
    return 0


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def command_report(args) -> int:
    index = load_index(args.index)
    source_lookup = {s["id"]: s for s in index["sources"]}
    out_lines = []

    out_lines.append("# Source Distiller Report\n")

    # Source map
    out_lines.append("## Source Map\n")
    out_lines.append("| ID | Source | Type | Lines |")
    out_lines.append("|---|---|---|---:|")
    for s in index["sources"]:
        out_lines.append(f"| {s['id']} | {s['display']} | {s['kind']} | {s['line_count']} |")
    out_lines.append("")

    # Top evidence per query
    if args.query:
        out_lines.append(f"## Evidence for: {args.query}\n")
        hits = score_chunks(index, args.query)[: args.top_k]
        if hits:
            for rank, (score, chunk) in enumerate(hits, 1):
                src = source_lookup[chunk["source_id"]]
                out_lines.append(f"### [{rank}] {citation(chunk)} (score={score:.1f}) — {src['display']}\n")
                out_lines.append("```")
                out_lines.append(chunk["text"][:800])
                out_lines.append("```\n")
        else:
            out_lines.append("No matching evidence found.\n")

    # Conflicts
    conflicts = find_conflicts(index, top_n=args.max_conflicts)
    if conflicts:
        out_lines.append("## Cross-Source Conflicts\n")
        out_lines.append("| # | Score | Source A | Source B | Numeric Conflicts |")
        out_lines.append("|---|---|---|---|---|")
        for i, c in enumerate(conflicts, 1):
            nums = "; ".join(f"{k}: {v}" for k, v in c["numeric_conflicts"]) or "—"
            out_lines.append(
                f"| {i} | {c['score']} | {c['source_a']} ({c['chunk_a']}) "
                f"| {c['source_b']} ({c['chunk_b']}) | {nums} |"
            )
        out_lines.append("")
    else:
        out_lines.append("## Cross-Source Conflicts\n")
        out_lines.append("No conflicts detected.\n")

    # Stats
    out_lines.append("## Index Stats\n")
    out_lines.append(f"- Sources: {len(index['sources'])}")
    out_lines.append(f"- Chunks: {index['chunk_count']}")
    out_lines.append(f"- Unique terms: {len(index.get('doc_freq', {}))}")
    out_lines.append("")

    report = "\n".join(out_lines)

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"Report written to {args.out}")
    else:
        print(report)
    return 0


# ---------------------------------------------------------------------------
# Chat (interactive REPL)
# ---------------------------------------------------------------------------

def command_chat(args) -> int:
    index = load_index(args.index)
    source_lookup = {s["id"]: s for s in index["sources"]}

    print(f"Source Distiller v{__version__} — Interactive Mode")
    print(f"Index: {len(index['sources'])} sources, {index['chunk_count']} chunks")
    print("Commands: /search <query> | /quote <S1:L10-L20> | /sources | /conflicts | /help | /quit\n")

    while True:
        try:
            line = input("sd> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue

        if line in ("/quit", "/exit", "/q"):
            break
        elif line == "/help":
            print("  /search <query>    Search for evidence")
            print("  /quote <cite>      Verify a citation (e.g. S1:L10-L20)")
            print("  /sources           List all indexed sources")
            print("  /conflicts         Detect cross-source conflicts")
            print("  /help              Show this help")
            print("  /quit              Exit")
            print("  <anything else>    Shortcut for /search")
        elif line == "/sources":
            for s in index["sources"]:
                print(f"  {s['id']}: {s['display']} ({s['kind']}, {s['line_count']} lines)")
        elif line == "/conflicts":
            conflicts = find_conflicts(index, top_n=10)
            if not conflicts:
                print("  No conflicts detected.")
            for i, c in enumerate(conflicts, 1):
                print(f"  #{i} (score={c['score']}) {c['chunk_a']} vs {c['chunk_b']}")
                if c["numeric_conflicts"]:
                    for key, vals in c["numeric_conflicts"]:
                        print(f"     numeric: {key} -> {vals}")
        elif line.startswith("/quote "):
            cite = line[7:].strip()
            try:
                sid, start, end = parse_cite(cite)
                source = next((s for s in index["sources"] if s["id"] == sid), None)
                if not source:
                    print(f"  Unknown source: {sid}")
                    continue
                extracted = extract_source(Path(source["path"]))
                lines = extracted.lines[start - 1 : end]
                print(f"  {cite} {source['display']}")
                for n, ln in enumerate(lines, start=start):
                    print(f"  {n}: {ln}")
            except ValueError as exc:
                print(f"  Error: {exc}")
        elif line.startswith("/search "):
            query = line[8:].strip()
            hits = score_chunks(index, query)[: args.top_k]
            if not hits:
                print("  No results.")
            for rank, (score, chunk) in enumerate(hits, 1):
                src = source_lookup[chunk["source_id"]]
                excerpt = chunk["text"][:200].replace("\n", " ")
                print(f"  [{rank}] {citation(chunk)} score={score:.1f} {src['display']}")
                print(f"      {excerpt}...")
        else:
            # Default: treat as search query
            hits = score_chunks(index, line)[: args.top_k]
            if not hits:
                print("  No results. Try different terms or /help.")
            for rank, (score, chunk) in enumerate(hits, 1):
                src = source_lookup[chunk["source_id"]]
                excerpt = chunk["text"][:200].replace("\n", " ")
                print(f"  [{rank}] {citation(chunk)} score={score:.1f} {src['display']}")
                print(f"      {excerpt}...")
    return 0


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def command_stats(args) -> int:
    index = load_index(args.index)
    print(f"version:      {index.get('version', '?')}")
    print(f"root:         {index.get('root', '?')}")
    print(f"sources:      {len(index['sources'])}")
    print(f"chunks:       {index['chunk_count']}")
    print(f"unique_terms: {len(index.get('doc_freq', {}))}")
    print()
    total_lines = 0
    for s in index["sources"]:
        total_lines += s["line_count"]
        print(f"  {s['id']}: {s['display']} ({s['kind']}, {s['line_count']} lines)")
    print(f"\ntotal_lines: {total_lines}")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="source-distiller",
        description="Zero-hallucination citation engine for multi-document research.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("index", help="Build a deterministic source index.")
    p.add_argument("path", help="File or directory to index.")
    p.add_argument("--out", default=".source-distiller/index.json", help="Output index path.")
    p.add_argument("--chunk-lines", type=int, default=40, help="Lines per chunk.")
    p.add_argument("--overlap", type=int, default=5, help="Overlap lines between chunks.")
    p.set_defaults(func=build_index)

    p = sub.add_parser("search", help="Retrieve top-k evidence chunks.")
    p.add_argument("--index", required=True, help="Path to index.json.")
    p.add_argument("--query", required=True, help="Search query.")
    p.add_argument("--top-k", type=int, default=8, help="Number of results.")
    p.add_argument("--max-chars", type=int, default=1200, help="Max chars per excerpt.")
    p.add_argument("--json", action="store_true", help="Output as JSON.")
    p.set_defaults(func=command_search)

    p = sub.add_parser("quote", help="Re-open a cited span for verification.")
    p.add_argument("--index", required=True, help="Path to index.json.")
    p.add_argument("--cite", required=True, help="Citation like S1:L10-L20.")
    p.set_defaults(func=command_quote)

    p = sub.add_parser("audit", help="Check a draft answer for citation issues.")
    p.add_argument("--index", required=True, help="Path to index.json.")
    p.add_argument("--answer", required=True, help="Path to answer markdown file.")
    p.add_argument("--min-block-chars", type=int, default=120, help="Min block size to flag.")
    p.add_argument("--max-uncited", type=int, default=10, help="Max uncited blocks to show.")
    p.add_argument("--strict-numbers", action=argparse.BooleanOptionalAction, default=True,
                   help="Check numeric claims against cited spans.")
    p.set_defaults(func=command_audit)

    p = sub.add_parser("conflicts", help="Detect cross-document disagreements.")
    p.add_argument("--index", required=True, help="Path to index.json.")
    p.add_argument("--min-similarity", type=float, default=0.15, help="Min Jaccard similarity.")
    p.add_argument("--top-n", type=int, default=20, help="Max conflicts to show.")
    p.add_argument("--json", action="store_true", help="Output as JSON.")
    p.set_defaults(func=command_conflicts)

    p = sub.add_parser("report", help="Generate a full evidence report.")
    p.add_argument("--index", required=True, help="Path to index.json.")
    p.add_argument("--query", default=None, help="Optional query to focus evidence.")
    p.add_argument("--top-k", type=int, default=10, help="Evidence results for query.")
    p.add_argument("--max-conflicts", type=int, default=10, help="Max conflicts in report.")
    p.add_argument("--out", default=None, help="Output file (default: stdout).")
    p.set_defaults(func=command_report)

    p = sub.add_parser("chat", help="Interactive search and quote REPL.")
    p.add_argument("--index", required=True, help="Path to index.json.")
    p.add_argument("--top-k", type=int, default=5, help="Results per search.")
    p.set_defaults(func=command_chat)

    p = sub.add_parser("stats", help="Quick index overview.")
    p.add_argument("--index", required=True, help="Path to index.json.")
    p.set_defaults(func=command_stats)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
