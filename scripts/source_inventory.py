#!/usr/bin/env python3
import sys
from pathlib import Path

TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".pdf", ".docx", ".html", ".htm",
    ".csv", ".tsv", ".json", ".yaml", ".yml", ".xml",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs",
}

def classify(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "document"
    if ext in {".md", ".txt", ".markdown"}:
        return "text"
    if ext in {".csv", ".tsv", ".json", ".yaml", ".yml", ".xml"}:
        return "data"
    if ext in {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs"}:
        return "code"
    if ext in {".html", ".htm"}:
        return "web"
    return "other"

def main() -> int:
    if len(sys.argv) != 2:
        print("usage: source_inventory.py <path>", file=sys.stderr)
        return 2

    root = Path(sys.argv[1]).expanduser().resolve()
    if not root.exists():
        print(f"not found: {root}", file=sys.stderr)
        return 1

    files = [p for p in root.rglob("*") if p.is_file() and not any(part.startswith(".git") for part in p.parts)]
    rows = []
    for p in files:
        rel = p.relative_to(root)
        kind = classify(p)
        size_kb = p.stat().st_size / 1024
        likely_readable = p.suffix.lower() in TEXT_EXTS
        rows.append((kind, likely_readable, size_kb, str(rel)))

    rows.sort(key=lambda r: (not r[1], r[0], r[3].lower()))
    print("| Kind | Readable | Size KB | Path |")
    print("|---|---:|---:|---|")
    for kind, readable, size_kb, rel in rows:
        print(f"| {kind} | {'yes' if readable else 'no'} | {size_kb:.1f} | `{rel}` |")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
