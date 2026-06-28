# Changelog

## 0.1.0 (2025-06-26)

Initial release.

### Features

- **index** — Build deterministic source index from PDF, DOCX, Markdown, HTML, code, CSV, JSON, YAML
- **search** — BM25-style retrieval with bigrams, returns top-k evidence with `S1:L10-L20` citations
- **quote** — Re-open any cited span to verify it before trusting
- **audit** — Catch fake source IDs, out-of-range lines, uncited paragraphs, numeric mismatches
- **conflicts** — Auto-detect cross-document disagreements via topic similarity + negation signals + numeric diff
- **report** — Generate full markdown report: source map + evidence + conflict matrix
- **chat** — Interactive REPL for real-time search, quote, and conflict checks
- **stats** — Quick index overview

### Details

- Zero external dependencies for core functionality
- PDF support via `pdftotext` (preferred) or `pypdf` (fallback)
- BM25-style TF-IDF with unigram + bigram terms
- Page-level anchors for PDF citations (`[p2:L14]`)
- 18 pytest tests, 12-point adversarial benchmark — all passing
- Designed as grounding layer for Claude Code, Cursor, ChatGPT, OpenAI Codex
