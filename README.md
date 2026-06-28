<p align="center">
  <h1 align="center">Source Distiller</h1>
  <p align="center">
    <strong>Zero-hallucination citation engine for multi-document research.</strong><br/>
    NotebookLM-style source grounding — in your terminal.
  </p>
</p>

<p align="center">
  <a href="https://pypi.org/project/source-distiller/"><img src="https://img.shields.io/pypi/v/source-distiller.svg?color=blue&label=PyPI" alt="PyPI"></a>
  <a href="https://github.com/emiroktay1/source-distiller/actions"><img src="https://img.shields.io/github/actions/workflow/status/emiroktay1/source-distiller/ci.yml?branch=main&label=CI" alt="CI"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+"></a>
</p>

<p align="center">
  <img src="assets/demo.gif" alt="Source Distiller Demo" width="800">
</p>

---

## The Problem

You drop 15 research papers into an LLM and ask a question. It:

- **Hallucinates** citations that don't exist in any source
- **Loses** information buried in the middle of long context ([Liu et al., 2023](https://arxiv.org/abs/2307.03172))
- **Flattens** real disagreements between sources into fake consensus
- **Burns** your entire token budget loading irrelevant pages

## The Solution

Source Distiller is a **deterministic, local-first CLI** that sits between your documents and your LLM. It indexes sources with line-level anchors, retrieves only relevant evidence, detects cross-document conflicts, and audits every citation before it reaches the user.

**No LLM calls. No cloud. No embeddings needed. No hallucinated references.**

### Real output from 15 academic papers (16,224 lines):

```
$ source-distiller index ./papers --out index.json
indexed 15 sources, 468 chunks -> index.json

$ source-distiller search --index index.json \
    --query "citation verification reduces hallucination" --top-k 3

[1] S4:L351-L390  score=19.842  source=CIVICA.pdf
    CIVICA achieved 92% citation precision, 91% citation coverage,
    and an 8% hallucination rate. Relative to citation-prompted RAG,
    CIVICA improved citation precision from 79% to 92% and reduced
    hallucination rate from 14% to 8%.

[2] S4:L316-L355  score=19.492  source=CIVICA.pdf
    Compared CIVICA against LLM-only, vanilla RAG, and citation-
    prompted RAG baselines using the same base generator...

[3] S4:L36-L75    score=18.160  source=CIVICA.pdf
    Unsupported claims are removed or restated using verified
    evidence only. On 1,200 consumer-law queries...

$ source-distiller quote --index index.json --cite S4:L351-L390
S4:L351-L390 CIVICA.pdf
351: [p5:L13] response accessibility for non-expert users.
352: [p5:L14] End-to-End Latency: Total response time from query...
353: [p5:L16] D. Quantitative Results
354: [p5:L17] Table I summarizes the main results. CIVICA achieved 92%
355: [p5:L18] citation precision, 91% citation coverage, and an 8% halluci-
356: [p5:L19] nation rate...

$ source-distiller conflicts --index index.json --top-n 3
Found 3 potential cross-source conflicts:

--- Conflict #1 (score=1.764) ---
  S3:L1331-L1370 [ALCE_Gao_2023.pdf]
  vs
  S13:L246-L285 [RAG_Lewis_2020.pdf]
  similarity=0.161  negation_signals=6
  numeric: table -> {'22', '10'} vs {'1'}

$ source-distiller audit --index index.json --answer draft.md
citations_found: 12
bad_citations: 0
possibly_uncited_blocks: 0
numeric_mismatches: 0
```

## Why Not Just Use...

| Tool | What It Does | What Source Distiller Does Differently |
|---|---|---|
| **NotebookLM** | Cloud-only, Google-proprietary, no CLI | Local, open-source, terminal-native, any agent |
| **RAGFlow / LangChain** | Full RAG stack, needs vector DB + LLM | Zero-dependency CLI, no LLM calls, deterministic |
| **Manual grep** | No semantic ranking, no citation tracking | BM25 scoring + citation audit + conflict detection |
| **Just paste into Claude** | Token-hungry, mid-context information loss | Index once, retrieve top-k, verify citations |

## Features

| Feature | Description |
|---|---|
| **8 commands** | `index` `search` `quote` `audit` `conflicts` `report` `chat` `stats` |
| **Line-level citations** | Every claim traced to `S1:L10-L20` with page anchors for PDFs |
| **Citation audit** | Catches fake sources, out-of-range lines, uncited paragraphs, numeric mismatches |
| **Conflict detection** | Auto-detects cross-document disagreements via topic similarity + negation + numeric diff |
| **Full reports** | One-command markdown report: source map + evidence + conflict matrix |
| **Interactive REPL** | `source-distiller chat` for real-time search, quote, and conflict checks |
| **Quote verification** | Re-opens cited spans so you (or your agent) can verify before trusting |
| **Token-efficient** | Index once, retrieve only top-k chunks — no full-doc context needed |
| **Multi-format** | PDF (`pdftotext` + `pypdf`), DOCX, Markdown, HTML, code, CSV, JSON, YAML |
| **Zero core deps** | Runs on Python stdlib. Optional `pypdf` for PDF fallback |
| **Agent-ready** | Built for Claude Code, Cursor, ChatGPT, and any CLI agent |

## Quick Start

```bash
pip install source-distiller
```

```bash
# Index your sources
source-distiller index ./my-papers --out index.json

# Search with a question
source-distiller search --index index.json --query "does retrieval reduce hallucination"

# Verify a citation before trusting it
source-distiller quote --index index.json --cite S4:L351-L390

# Detect conflicts across your sources
source-distiller conflicts --index index.json

# Generate a full evidence report
source-distiller report --index index.json --query "citation methods" --out report.md

# Audit a draft answer for bad citations
source-distiller audit --index index.json --answer draft.md

# Interactive mode
source-distiller chat --index index.json
```

<details>
<summary><strong>Install from source</strong></summary>

```bash
git clone https://github.com/emiroktay1/source-distiller.git
cd source-distiller
pip install -e ".[pdf]"
```

</details>

## How It Works

```
 Documents (PDF, MD, DOCX, HTML, code...)
        |
        v
 +--------------+
 |    INDEX      |  Deterministic chunking with line anchors + bigram terms
 +--------------+  BM25-style TF-IDF scoring, no embeddings needed
        |
        v
 +--------------+
 |    SEARCH     |  Top-k retrieval with source ID + line citations
 +--------------+
        |
   +----+----+
   v         v
 +--------+ +------------+
 | QUOTE  | | CONFLICTS  |  Re-open cited span     Auto-detect cross-doc
 +--------+ +------------+  to verify support      disagreements
   |         |
   v         v
 +--------------+
 |    AUDIT     |  Catch fake citations, uncited claims, numeric drift
 +--------------+
        |
        v
 +--------------+
 |    REPORT    |  Source map + evidence + conflict matrix in markdown
 +--------------+
```

## Interactive Mode

```
$ source-distiller chat --index index.json

Source Distiller v0.1.0 — Interactive Mode
Index: 15 sources, 468 chunks
Commands: /search <query> | /quote <S1:L10-L20> | /sources | /conflicts | /help | /quit

sd> citation verification hallucination
  [1] S4:L351-L390 score=19.8 CIVICA.pdf
      CIVICA achieved 92% citation precision, 91% citation coverage...
  [2] S4:L316-L355 score=19.5 CIVICA.pdf
      Compared CIVICA against LLM-only, vanilla RAG...

sd> /quote S4:L351-L390
  S4:L351-L390 CIVICA.pdf
  351: [p5:L13] response accessibility for non-expert users.
  352: [p5:L17] Table I summarizes the main results...

sd> /conflicts
  #1 (score=1.764) S3:L1331-L1370 vs S13:L246-L285
     numeric: table -> {'22', '10'} vs {'1'}
```

## Agent Integration

Source Distiller is designed as a **grounding layer for AI agents**. It gives any LLM tool a way to cite, verify, and audit claims against real sources.

<details>
<summary><strong>Claude Code / CLI Agents</strong></summary>

```bash
# Add to your agent prompt:
source-distiller index ./sources --out index.json
source-distiller search --index index.json --query "$USER_QUESTION" --json
source-distiller quote --index index.json --cite S1:L10-L25
source-distiller audit --index index.json --answer answer.md
```

</details>

<details>
<summary><strong>Cursor / AI IDE</strong></summary>

Add to `.cursorrules`:
```
When answering from documents, use source-distiller CLI to:
1. Index sources once
2. Search for relevant evidence with --json flag
3. Quote-check every citation before including it
4. Run audit on the final answer before presenting it
```

</details>

## Research Foundation

This tool operationalizes findings from peer-reviewed research:

| Paper | Key Insight | How We Use It |
|---|---|---|
| [Lost in the Middle (Liu 2023)](https://arxiv.org/abs/2307.03172) | Models lose info buried in mid-context | Source mapping + top-k retrieval prevents positional bias |
| [RAG (Lewis 2020)](https://arxiv.org/abs/2005.11401) | Retrieval improves factuality | Index + search instead of dumping full docs into context |
| [Self-RAG (Asai 2023)](https://arxiv.org/abs/2310.11511) | Critique gates reduce hallucination | Quote-check and audit steps |
| [ALCE (Gao 2023)](https://arxiv.org/abs/2305.14627) | Citation presence != citation correctness | Audit catches fake/invalid citations |
| [AIS (Rashkin 2023)](https://aclanthology.org/2023.cl-4.2/) | Attribution needs identified sources | Stable S1/S2/S3 source IDs with line anchors |
| [CIVICA (2025)](https://ieeexplore.ieee.org) | Explicit verification > prompt-level citation | Verification/repair pipeline inspiration |

## Benchmark

```bash
python -m source_distiller.evaluate
```

Adversarial smoke-test with superseded policies, conflicting documents, fake citations, and semantic traps:

```
retrieval_score:    6/6  = 100%
quote_score:        1/1  = 100%
audit_score:        2/2  = 100%
conflicts_score:    1/1  = 100%
report_score:       1/1  = 100%
semantic_score:     1/1  = 100%
mechanical_total:  11/11 = 100%
overall_score:     12/12 = 100%
```

```bash
python -m pytest tests/ -v   # 18 tests, all passing
```

> These are controlled smoke-tests, not claims of real-world perfection. See [Limitations](#limitations).

## Output Shapes

Source Distiller defines three structured output templates for agents:

| Shape | Use When | Sections |
|---|---|---|
| **Full Source Synthesis** | Research review, many sources, conflicts matter | Source Map + Evidence Ledger + Conflict Matrix + Answer + Caveats |
| **Focused Answer** | Direct question from many sources | Short Answer + Evidence + Conflicts/Gaps |
| **Compatibility Audit** | "Do these sources agree?" | Summary + Conflict Matrix + Canonical Recommendation |

See [`docs/protocol.md`](docs/protocol.md) for the complete protocol and checklist.

## Limitations

- **Lexical retrieval only.** BM25-style scoring with bigrams. Paraphrases and synonyms may be missed. Use multiple query phrasings.
- **No semantic entailment.** Audit checks citation validity (exists, in range, numbers match) but cannot verify that a cited passage actually supports the claim. The agent must verify semantic support.
- **PDF text quality.** Depends on `pdftotext` or `pypdf` extraction. Scanned PDFs without OCR will produce empty output.
- **Conflict detection is heuristic.** Uses term overlap + negation signals + numeric comparison. Not a logical contradiction prover.

## Roadmap

- [ ] Hybrid retrieval (lexical + lightweight embeddings)
- [ ] Semantic entailment scoring
- [ ] `source-distiller watch` — auto-reindex on file changes
- [ ] VS Code extension
- [ ] Web UI for non-terminal users

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome.

## License

[MIT](LICENSE)
