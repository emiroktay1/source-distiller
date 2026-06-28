# Source Distiller Protocol

Complete protocol reference for agents using Source Distiller.

For the full protocol, see [`../references/protocol.md`](../references/protocol.md).

For the research basis, see [`../references/research-basis.md`](../references/research-basis.md).

## Quick Reference

### Commands

| Command | Purpose | Example |
|---|---|---|
| `index` | Build deterministic source index | `source-distiller index ./papers --out index.json` |
| `search` | Retrieve top-k evidence chunks | `source-distiller search --index index.json --query "..."` |
| `quote` | Re-open a cited span for verification | `source-distiller quote --index index.json --cite S1:L10-L20` |
| `audit` | Check draft for citation issues | `source-distiller audit --index index.json --answer draft.md` |

### Citation Format

- `S1` - Source only
- `S1:L10-L20` - Source with line range
- `S1: p. 4` - Source with page (PDF)
- `[S1, S3: section 2.1]` - Multiple sources

### Output Shapes

1. **Full Source Synthesis** - Source Map + Evidence Ledger + Conflict Matrix + Answer + Caveats
2. **Focused Answer** - Short Answer + Evidence + Conflicts/Gaps
3. **Source Compatibility Audit** - Compatibility Summary + Conflict Matrix + Canonical Recommendation

### Audit Checks

- Unknown source IDs (e.g., `S99` when only S1-S15 exist)
- Out-of-range line spans (e.g., `S1:L1-L9999` when source has 100 lines)
- Uncited long paragraphs (>120 chars with no citation)
- Numeric mismatches (numbers in text not found in cited spans)
