# Using Source Distiller as an Agent Grounding Layer

This guide shows how to integrate Source Distiller into AI agent workflows
so that every claim is cited, verified, and auditable.

## The Workflow

```
User Question
     |
     v
[1] source-distiller search --query "..." --json
     |
     v
[2] Agent reads top-k evidence chunks
     |
     v
[3] Agent drafts answer with S1:L10-L20 citations
     |
     v
[4] source-distiller quote --cite S1:L10-L20  (verify each citation)
     |
     v
[5] source-distiller audit --answer draft.md   (catch any mistakes)
     |
     v
Verified Answer with Citations
```

## Claude Code Example

Add this to your project's `SKILL.md` or `CLAUDE.md`:

```markdown
## Source-Grounded Answers

When the user asks a question about the indexed sources:

1. Search for evidence:
   source-distiller search --index index.json --query "$QUESTION" --json --top-k 8

2. Read the returned evidence chunks carefully.

3. Draft an answer citing each claim as [S1:L10-L20].

4. Before finalizing, verify important citations:
   source-distiller quote --index index.json --cite S1:L10-L20

5. Audit the final answer:
   source-distiller audit --index index.json --answer answer.md

6. If audit reports bad_citations > 0, fix them before responding.
```

## Cursor Example

Add to `.cursorrules`:

```
When answering questions from project documents:
- Run: source-distiller search --index index.json --query "<question>" --json
- Cite every claim with the source ID and line range from search results
- Run: source-distiller audit --index index.json --answer <your-answer-file>
- Fix any flagged citations before presenting the answer
```

## OpenAI Codex CLI Example

In your agent's system prompt or codex.yaml:

```yaml
tools:
  - name: search_sources
    command: source-distiller search --index index.json --query "{query}" --json --top-k 8
  - name: verify_citation
    command: source-distiller quote --index index.json --cite "{citation}"
  - name: audit_answer
    command: source-distiller audit --index index.json --answer "{answer_file}"
```

## Key Rules for Agents

1. **Never cite from memory.** Only cite source IDs and line ranges returned by `search`.
2. **Quote-check before trusting.** Run `quote` on critical citations to see the actual text.
3. **Audit before responding.** The `audit` command catches fake sources, impossible line ranges, and uncited long blocks.
4. **Use conflicts to flag disagreements.** Run `conflicts` when multiple sources discuss the same topic.
5. **Prefer primary sources.** If search returns both a summary and a primary source, cite the primary.
