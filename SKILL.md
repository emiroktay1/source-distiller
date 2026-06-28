---
name: source-distiller
description: Distill large, messy, or multi-document source sets into task-relevant, cited evidence before answering. Use when the user provides many papers, PDFs, docs, links, transcripts, notes, screenshots, code files, or mixed sources and asks to understand, summarize, compare, synthesize, fact-check, extract decisions, detect agreement/conflict across documents, build an argument, or answer from those sources without getting confused by irrelevant context.
---

# Source Distiller

Use this skill to prevent context overload. Do not try to "understand everything" at once. First build a source map, then extract only evidence relevant to the user's task. Every non-trivial claim in the final answer must cite the source ids that support it.

## Core Protocol

1. Restate the user's task as a narrow evidence question.
2. Inventory the sources before synthesis:
   - source id
   - title/path/link
   - source type
   - date/version if visible
   - likely relevance: high, medium, low, unknown
   - reason for relevance
3. Triage reading depth:
   - **High relevance**: inspect closely.
   - **Medium relevance**: skim for named entities, methods, claims, numbers, and conclusions.
   - **Low relevance**: ignore unless a gap appears.
   - **Unknown**: sample the beginning, headings, metadata, and conclusion.
4. Build an evidence ledger with compact notes:
   - claim
   - supporting source id(s)
   - location if available
   - confidence
   - caveat
5. Build a conflict matrix before synthesis when two or more sources address the same issue:
   - issue
   - agreeing sources
   - conflicting sources
   - difference type: factual, definitional, methodological, temporal, scope, interpretation, or missing evidence
   - resolution: reconciled, unresolved, source-quality preference, or needs verification
6. Separate contradictions from synthesis:
   - If sources disagree, state the disagreement and why one source may be stronger.
   - Do not flatten disagreement into a fake consensus.
7. Answer from the ledger, not from memory.
8. End with gaps only when the gaps affect the answer.

## Citation Contract

Use stable ids: `S1`, `S2`, `S3`. If locations are available, cite as `S1: p. 4`, `S2: section 2.1`, `S3: lines 120-140`, or `S4: 00:13:22`.

Every final-answer claim that depends on the source set must cite at least one source id. Strong comparative claims must cite all compared sources. If a claim is an inference, write `Inference from S1, S3:` before the claim.

Do not cite:
- source ids that were only skimmed and did not support the claim
- irrelevant sources merely because they were provided
- sources that contradict the claim unless the contradiction is explicitly discussed

If the user asks for a citation-free executive summary, keep a cited evidence ledger internally and include a short "Citations available on request" note only if appropriate.

## Required Output Shapes

Use one of these shapes. Do not leave placeholder headings empty.

### Full Source Synthesis

Use for research reviews, due diligence, many documents, or when conflicts matter.

```markdown
**Source Map**
| ID | Source | Type | Date/Version | Relevance | Role |
|---|---|---|---|---|---|
| S1 | ... | paper/doc/etc. | ... | High/Medium/Low | supports/challenges/background |

**Evidence Ledger**
| Claim | Support | Location | Confidence | Caveat |
|---|---|---|---|---|
| ... | S1, S3 | ... | High/Medium/Low | ... |

**Agreement And Conflict Matrix**
| Issue | Agreement | Conflict | Difference Type | Resolution |
|---|---|---|---|---|
| ... | S1, S2 | S4 | temporal/scope/etc. | unresolved/reconciled/etc. |

**Answer**
Write the answer with citations in every source-dependent paragraph. Example: "The policy changed after the 2024 revision, so older implementation notes should not be treated as current [S2: changelog, S5: p. 3]."

**Caveats**
List only caveats that change the answer.
```

### Focused Answer

Use when the user wants a direct answer from many sources.

```markdown
**Short Answer**
Answer directly with citations in each paragraph.

**Evidence**
- Claim ... [S1: location]
- Claim ... [S2, S4: location]

**Conflicts Or Gaps**
- Conflict/gap ... [S2 vs S3]
```

### Source Compatibility Audit

Use when the user asks whether sources agree, conflict, duplicate, supersede, or validate each other.

```markdown
**Compatibility Summary**
State whether the set is broadly consistent, partly conflicting, or materially conflicting.

**Conflict Matrix**
| Issue | Source A | Source B | Relationship | Severity | What To Do |
|---|---|---|---|---|---|
| ... | S1 | S2 | agrees/conflicts/supersedes | low/medium/high | ... |

**Canonical Source Recommendation**
Name the source(s) to treat as authoritative and why.
```

## Rules

- Do not cite or rely on a source just because it was provided.
- Do not summarize every source unless the user asks for a literature review.
- Do not mix direct source claims with your own inference; label inferences.
- Do not over-weight abstracts, introductions, marketing copy, or executive summaries when methods/results are available.
- Prefer primary sources over summaries, blog posts, slides, or secondary commentary.
- Preserve uncertainty when source quality, date, scope, or methodology is weak.
- Treat newer versions, official docs, peer-reviewed results, and direct datasets as stronger only when their scope matches the task.
- If the task is current, legal, medical, financial, or otherwise time-sensitive, verify with current primary sources when browsing is available.
- Never present consensus unless the conflict matrix shows no material contradictions among high-relevance sources.

## Reference

For a stricter checklist, read `references/protocol.md`.

For research grounding behind this skill, read `references/research-basis.md`.

## CLI Tool

Install: `pip install source-distiller`

For cited retrieval and verification from terminal-based agents such as Codex, Claude Code, Cursor, or ChatGPT with shell access:

```bash
# Build a deterministic local source index.
source-distiller index ./sources --out index.json

# Retrieve compact evidence with line citations.
source-distiller search --index index.json --query "the user's question" --top-k 8

# Re-open a cited span exactly before relying on it.
source-distiller quote --index index.json --cite S1:L10-L25

# Check a drafted answer for fake/out-of-range citations and uncited long paragraphs.
source-distiller audit --index index.json --answer answer.md

# Run the controlled benchmark.
python -m source_distiller.evaluate
```

Use this workflow to keep token use low: index once, retrieve only top evidence chunks, quote-check cited spans, then answer. The CLI checks fake citations, out-of-range line spans, citation-free long blocks, and strict numeric mismatches by default. It is still not a complete semantic proof system; the agent must verify that each cited excerpt actually supports the claim.
