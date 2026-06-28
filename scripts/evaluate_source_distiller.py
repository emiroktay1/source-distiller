#!/usr/bin/env python3
"""
Benchmark Source Distiller on a controlled source set.

The benchmark is intentionally small but adversarial:
- superseded policies
- direct conflicts across documents
- irrelevant distractor text
- fake/out-of-range citations
- a real citation attached to a false claim

It reports mechanical grounding strength separately from semantic support,
because line-valid citations alone are not the same as proof that a claim is true.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CLI = ROOT / "source_distiller.py"


FIXTURES = {
    "01_policy_v1.md": """# Data Policy v1
Version: 2024-01-10
Status: superseded by Data Policy v2 on 2025-06-01
Audit logs are retained for 30 days.
EU users require explicit consent before analytics tracking.
File exports are limited to 10 MB.
The privacy officer for this policy is Alice Demir.
""",
    "02_policy_v2.md": """# Data Policy v2
Version: 2025-06-01
Status: current
This document replaces Data Policy v1.
Audit logs are retained for 90 days.
EU users require explicit consent before analytics tracking.
File exports are limited to 50 MB.
The privacy officer for this policy is Bora Kaya.
""",
    "03_engineering_notes.md": """# Engineering Notes
Date: 2025-06-03
The backend export endpoint still enforces a 10 MB file limit.
The engineering team marked this as a legacy implementation gap.
The gap conflicts with Data Policy v2 and should be fixed before launch.
""",
    "04_security_controls.md": """# Security Controls
Customer records are encrypted at rest with AES-256.
TLS 1.3 is required for data in transit.
Audit logs are stored in a separate append-only stream.
""",
    "05_marketing_copy.md": """# Marketing Copy
Glokal helps organizations turn complexity into clear action.
The brochure discusses strategic communications and stakeholder alignment.
It does not define data retention or export limits.
""",
    "06_meeting_transcript.md": """# Meeting Transcript
00:02 Emir: We should cite sources line by line in public answers.
00:04 Aylin: For conflict checks, compare current policy against implementation notes.
00:06 Emir: Do not treat marketing copy as a source of compliance requirements.
""",
}


RETRIEVAL_CASES = [
    {
        "name": "current retention",
        "query": "current audit logs retained 90 days policy v2",
        "must_have_top3": {"02_policy_v2.md"},
    },
    {
        "name": "export conflict",
        "query": "file exports limited 50 MB backend still enforces 10 MB conflict",
        "must_have_top5": {"02_policy_v2.md", "03_engineering_notes.md"},
    },
    {
        "name": "EU analytics consent",
        "query": "EU users explicit consent before analytics tracking",
        "must_have_top3": {"02_policy_v2.md"},
    },
    {
        "name": "encryption control",
        "query": "customer records encrypted at rest AES-256",
        "must_have_top1": {"04_security_controls.md"},
    },
    {
        "name": "source citation instruction",
        "query": "cite sources line by line public answers",
        "must_have_top3": {"06_meeting_transcript.md"},
    },
    {
        "name": "irrelevant query",
        "query": "pricing discounts invoice renewal coupon",
        "expect_empty": True,
    },
]


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check)


def write_fixtures(base: Path) -> Path:
    src = base / "sources"
    src.mkdir()
    for name, text in FIXTURES.items():
        (src / name).write_text(text, encoding="utf-8")
    return src


def index_sources(src: Path, out: Path) -> dict:
    run([sys.executable, str(CLI), "index", str(src), "--out", str(out)])
    return json.loads(out.read_text(encoding="utf-8"))


def search(index: Path, query: str, top_k: int = 5) -> list[dict]:
    proc = run([
        sys.executable,
        str(CLI),
        "search",
        "--index",
        str(index),
        "--query",
        query,
        "--top-k",
        str(top_k),
        "--json",
    ])
    return json.loads(proc.stdout)


def find_citation(index_data: dict, source_name: str, phrase: str) -> str:
    source = next(s for s in index_data["sources"] if s["display"] == source_name)
    lines = Path(source["path"]).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, start=1):
        if phrase in line:
            return f"{source['id']}:L{i}-L{i}"
    raise RuntimeError(f"phrase not found in {source_name}: {phrase}")


def evaluate_retrieval(index: Path) -> tuple[int, int, list[str]]:
    passed = 0
    total = len(RETRIEVAL_CASES)
    details = []
    for case in RETRIEVAL_CASES:
        hits = search(index, case["query"], top_k=5)
        top_sources = [h["source"] for h in hits]
        ok = True
        if case.get("expect_empty"):
            ok = len(hits) == 0
        if "must_have_top1" in case:
            ok = ok and bool(top_sources) and top_sources[0] in case["must_have_top1"]
        if "must_have_top3" in case:
            ok = ok and case["must_have_top3"].issubset(set(top_sources[:3]))
        if "must_have_top5" in case:
            ok = ok and case["must_have_top5"].issubset(set(top_sources[:5]))
        passed += int(ok)
        details.append(f"{'PASS' if ok else 'FAIL'} retrieval:{case['name']} -> {top_sources[:5]}")
    return passed, total, details


def evaluate_quote(index: Path, index_data: dict) -> tuple[int, int, list[str]]:
    cite = find_citation(index_data, "02_policy_v2.md", "Audit logs are retained for 90 days.")
    proc = run([sys.executable, str(CLI), "quote", "--index", str(index), "--cite", cite])
    ok = "Audit logs are retained for 90 days." in proc.stdout
    return int(ok), 1, [f"{'PASS' if ok else 'FAIL'} quote exact span -> {cite}"]


def evaluate_audit(index: Path, index_data: dict, base: Path) -> tuple[int, int, list[str]]:
    cite = find_citation(index_data, "02_policy_v2.md", "Audit logs are retained for 90 days.")
    good = base / "good_answer.md"
    good.write_text(f"Audit logs are retained for 90 days [{cite}].\n", encoding="utf-8")
    good_proc = run([sys.executable, str(CLI), "audit", "--index", str(index), "--answer", str(good)], check=False)
    good_ok = good_proc.returncode == 0 and "bad_citations: 0" in good_proc.stdout

    bad = base / "bad_answer.md"
    bad.write_text(
        "This paragraph cites a missing source [S99:L1-L2].\n\n"
        "This paragraph cites an impossible line span [S2:L1-L9999].\n\n"
        "This long paragraph deliberately has no citation even though it states a source-dependent claim about policy behavior and should therefore be flagged by the audit command.\n",
        encoding="utf-8",
    )
    bad_proc = run([sys.executable, str(CLI), "audit", "--index", str(index), "--answer", str(bad)], check=False)
    bad_ok = (
        bad_proc.returncode == 1
        and "unknown source" in bad_proc.stdout
        and "line range outside" in bad_proc.stdout
        and "possibly_uncited_blocks: 1" in bad_proc.stdout
    )

    return int(good_ok) + int(bad_ok), 2, [
        f"{'PASS' if good_ok else 'FAIL'} audit accepts well-cited answer",
        f"{'PASS' if bad_ok else 'FAIL'} audit rejects fake/out-of-range/uncited answer",
    ]


def evaluate_semantic_gap(index: Path, index_data: dict, base: Path) -> tuple[int, int, list[str]]:
    cite = find_citation(index_data, "02_policy_v2.md", "Audit logs are retained for 90 days.")
    false_answer = base / "false_but_cited.md"
    false_answer.write_text(f"Audit logs are retained for 365 days [{cite}].\n", encoding="utf-8")
    proc = run([sys.executable, str(CLI), "audit", "--index", str(index), "--answer", str(false_answer)], check=False)
    detected = proc.returncode != 0
    # Current CLI is expected NOT to catch this: it validates citation mechanics, not semantic entailment.
    return int(detected), 1, [
        f"{'PASS' if detected else 'KNOWN GAP'} semantic false claim with real citation"
    ]


def pct(passed: int, total: int) -> float:
    return round((passed / total) * 100, 1) if total else 0.0


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        src = write_fixtures(base)
        index_path = base / "index.json"
        index_data = index_sources(src, index_path)

        sections = []
        r_pass, r_total, r_details = evaluate_retrieval(index_path)
        q_pass, q_total, q_details = evaluate_quote(index_path, index_data)
        a_pass, a_total, a_details = evaluate_audit(index_path, index_data, base)
        s_pass, s_total, s_details = evaluate_semantic_gap(index_path, index_data, base)

        sections.extend(r_details)
        sections.extend(q_details)
        sections.extend(a_details)
        sections.extend(s_details)

        mechanical_pass = r_pass + q_pass + a_pass
        mechanical_total = r_total + q_total + a_total
        full_pass = mechanical_pass + s_pass
        full_total = mechanical_total + s_total

        print("# Source Distiller Benchmark")
        print(f"sources: {len(index_data['sources'])}")
        print(f"chunks: {len(index_data['chunks'])}")
        print()
        print(f"retrieval_score: {r_pass}/{r_total} = {pct(r_pass, r_total)}%")
        print(f"quote_score: {q_pass}/{q_total} = {pct(q_pass, q_total)}%")
        print(f"audit_score: {a_pass}/{a_total} = {pct(a_pass, a_total)}%")
        print(f"semantic_support_score: {s_pass}/{s_total} = {pct(s_pass, s_total)}%")
        print(f"mechanical_grounding_score: {mechanical_pass}/{mechanical_total} = {pct(mechanical_pass, mechanical_total)}%")
        print(f"notebooklm_style_score: {full_pass}/{full_total} = {pct(full_pass, full_total)}%")
        print()
        for detail in sections:
            print("-", detail)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
