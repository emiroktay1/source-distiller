# Contributing to Source Distiller

Thanks for your interest in contributing.

## Getting Started

```bash
git clone https://github.com/emiroktay1/source-distiller.git
cd source-distiller
pip install -e ".[dev]"
```

## Running Tests

```bash
python -m pytest tests/
python -m source_distiller.evaluate  # benchmark
```

## Pull Request Process

1. Fork the repo and create a feature branch.
2. Make your changes. Keep PRs focused on a single concern.
3. Ensure the benchmark passes: `python -m source_distiller.evaluate`
4. Submit a PR with a clear description of what changed and why.

## Code Style

- Python 3.9+ compatible.
- No unnecessary dependencies — the core must run on stdlib alone.
- Type hints where they clarify intent.

## Areas for Contribution

- Hybrid retrieval (lexical + embedding)
- Semantic entailment checking
- Additional file format support
- Agent integration examples
- Documentation improvements
