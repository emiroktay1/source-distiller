# Research Basis

This skill operationalizes lessons from long-context, retrieval, grounding, and conflicting-evidence research. Use this file when refining the skill or explaining why its workflow exists.

## Core Findings

- **Long context does not guarantee robust source use.** "Lost in the Middle" shows that models can perform worse when relevant information appears in the middle of long contexts, even with long-context models. Practical implication: build an explicit source map and re-check relevant middle-context sources. Source: https://arxiv.org/abs/2307.03172

- **Retrieval improves factuality but creates selection risk.** Retrieval-Augmented Generation (RAG) combines model generation with retrieved non-parametric memory. Practical implication: retrieve or inspect sources, but do not blindly include every retrieved passage. Source: https://arxiv.org/abs/2005.11401

- **Relevance and critique gates matter.** Self-RAG frames generation as retrieve, generate, and critique, including decisions about whether retrieval is needed and whether retrieved passages support output. Practical implication: use an evidence ledger and final citation check. Source: https://arxiv.org/abs/2310.11511

- **Conflicting evidence is a first-class problem.** Recent conflicting-evidence RAG work highlights ambiguity, misinformation, noisy documents, and inter-document conflicts. Practical implication: use a conflict matrix instead of collapsing disagreement into a single answer. Source: https://arxiv.org/abs/2504.13079

- **Citation-looking output is not necessarily verified.** Verifiability research evaluates whether generated statements are supported by attached citations and whether the citations are sufficient. Practical implication: require paragraph-level citations plus post-hoc citation audit. Source: https://aclanthology.org/2023.cl-4.2/

- **Attribution needs identified sources.** AIS-style attribution treats a statement as acceptable only when it is attributable to an identified source. Practical implication: cite source ids and exact locations, then quote-check important claims. Source: https://aclanthology.org/2023.cl-4.2/

## Design Implications

1. Source mapping before synthesis reduces positional and attention bias.
2. Citation requirements reduce unsupported synthesis.
3. Conflict classification prevents false consensus.
4. Source-quality ranking prevents weak secondary sources from overruling primary evidence.
5. A final citation audit catches claims that drift away from evidence.
6. Terminal retrieval with line anchors keeps token use low and makes hallucinations easier to detect.

## Useful Search Terms

- "Lost in the Middle: How Language Models Use Long Contexts"
- "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
- "Self-RAG Learning to Retrieve Generate and Critique"
- "Retrieval-Augmented Generation with Conflicting Evidence"
- "knowledge conflicts large language models survey"
- "Evaluating Verifiability in Generative Search Engines"
- "Attributable to Identified Sources AIS"
- "citation precision citation recall generative search"
