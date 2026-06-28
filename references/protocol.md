# Source Distiller Protocol

## Decision Tree

1. **Is the user asking about all sources or a specific question?**
   - All sources: produce a literature/source review.
   - Specific question: filter aggressively.

2. **Are there more than 5 substantial sources?**
   - Yes: create a source map before reading deeply.
   - No: read normally but still keep evidence notes.

3. **Are sources heterogeneous?**
   - Papers: focus on abstract, method, results, limitations.
   - Docs: focus on requirements, APIs, guarantees, constraints.
   - Transcripts/notes: focus on decisions, commitments, dates, speakers.
   - Code: focus on interfaces, data flow, call sites, tests.

4. **Does source quality vary?**
   - Rank by authority, date, directness, method quality, and relevance.

## Evidence Ledger Fields

Use this compact format internally or visibly:

| Claim | Support | Location | Confidence | Caveat |
|---|---|---|---|---|

Confidence:
- High: directly supported by a primary/source-specific passage.
- Medium: supported but with scope limits or indirectness.
- Low: inferred, partial, outdated, or contradicted.

## Citation Requirements

Final answers must cite source-dependent claims. Cite at paragraph or bullet level, not only in a bibliography. Use source ids and locations when available:

- `[S1]` when only the source is known.
- `[S1: p. 4]` for PDFs/books.
- `[S2: section "API limits"]` for docs.
- `[S3: lines 40-58]` for code.
- `[S4: 00:12:04]` for audio/video transcripts.

If a claim combines sources, cite all material sources: `[S1: p. 4; S3: table 2]`.

If the answer uses inference, label it:

`Inference from S1 and S3: ...`

## Agreement And Conflict Taxonomy

Classify source relationships before synthesizing:

- **Agreement**: same claim, compatible scope and time.
- **Complement**: different pieces fit together without contradiction.
- **Temporal supersession**: newer source updates or replaces older source.
- **Scope mismatch**: claims differ because populations, settings, APIs, jurisdictions, or versions differ.
- **Definition mismatch**: sources use the same term differently.
- **Method mismatch**: results differ because methods, measurements, or assumptions differ.
- **Direct factual conflict**: same scope/time, incompatible factual claims.
- **Unsupported assertion**: one source claims something without evidence.
- **Noise/irrelevance**: source is retrieved/provided but does not bear on the task.

Conflict severity:

- **High**: changes the answer, recommendation, risk assessment, or implementation.
- **Medium**: changes interpretation or confidence.
- **Low**: stylistic, terminology, or non-material details.

Resolution options:

- **Reconciled**: explain why both can be true.
- **Superseded**: prefer newer/authoritative source.
- **Prefer primary**: prefer direct evidence over summary.
- **Unresolved**: preserve disagreement; do not choose.
- **Needs verification**: browse/check primary source or request missing data.

## Anti-Confusion Tactics

- Use stable source ids: S1, S2, S3.
- Keep irrelevant source notes out of the final answer.
- Resolve terminology differences before comparing claims.
- Extract numbers with units and date/context.
- When two sources use different populations/scopes, do not call that a contradiction.
- When a source has a conclusion but weak method details, lower confidence.
- Re-check sources placed in the middle of a long context; do not assume they were used correctly.
- Prefer a small cited evidence set over a large uncited summary.

## Final Answer Checklist

Before finalizing:

- Does every major claim trace back to at least one source?
- Does every source-dependent paragraph/bullet include citations?
- Did you exclude irrelevant sources?
- Did you identify source conflicts?
- Did you classify conflicts by type and severity?
- Did you distinguish source claims from inference?
- Did you state material gaps?
- Is the answer shorter than the source map unless the user asked for a full review?

## Terminal Verification Workflow

Use `scripts/source_distiller.py` when the source set is local and large.

1. `index`: create source ids and line-based chunks once.
2. `search`: retrieve only the most relevant chunks for the user's question.
3. `quote`: re-open every important citation before using it in the final answer.
4. `audit`: check final drafts for unknown/out-of-range citations and uncited long paragraphs.

This workflow reduces token use by sending only selected excerpts into the model context. It also lowers hallucination risk by forcing citations to refer to real spans in the source set. By default, `audit` also flags numeric claims in cited paragraphs when the cited source spans do not contain the same numbers or measurements.

Limitations:

- Lexical retrieval can miss paraphrases; use multiple queries and synonyms.
- Citation existence does not prove semantic support; the agent must verify support.
- Strict numeric audit catches many false quantitative claims, but not all semantic contradictions.
- PDF line anchors depend on `pdftotext`; cite pages when exact line fidelity is weak.
- The workflow cannot guarantee zero hallucination, but it can make unsupported claims detectable.

## Benchmark

Run:

```bash
python3 scripts/evaluate_source_distiller.py
```

The benchmark creates a controlled six-document corpus with superseded policies, implementation conflicts, distractor text, bad citations, uncited claims, and a false numeric claim attached to a real citation. Treat a perfect score here as a smoke-test pass, not proof of real-world perfection.
