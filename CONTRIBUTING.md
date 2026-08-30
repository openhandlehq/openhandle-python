# Contributing

Thank you for improving the OpenHandle Python SDK.

## Development

Install Python 3.10 or newer, then run:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e . --group dev
python scripts/generate.py
pytest
```

Run `python scripts/generate.py` after changing the pinned OpenAPI document or
generator. Generated files must be committed with their source changes.

Quality checks:

```bash
ruff check .
ruff format --check .
mypy
python scripts/generate.py --check
python scripts/score_agent_eval.py evals/reference
```

## Commits

Use Conventional Commits. `feat` changes produce minor releases, `fix` changes
produce patch releases, and a `!` or `BREAKING CHANGE` footer produces a major
release.

API contract changes normally arrive as automated pull requests. Runtime,
typing, documentation, and example improvements are welcome directly.
