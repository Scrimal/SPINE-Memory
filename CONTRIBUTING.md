# Contributing

SPINE-Memory is a zero-dependency Markdown/YAML graph memory. Keep the core
runnable on the Python standard library.

## Setup

```bash
git clone https://github.com/Scrimal/SPINE-Memory.git
cd SPINE-Memory
pip install -e .[dev]
```

## Before opening a PR

```bash
# 1. smoke tests
python -m unittest

# 2. node quality audit (validates YAML, anchors, vectors, sections)
bash tools/_critic_check.sh nodes raw anchors/anchor_dump.json

# 3. build (run in /tmp to avoid polluting the repo)
python -m build
```

## Pull request requirements

- One logical change per PR.
- New `nodes/*.md` must pass `tools/_critic_check.sh` and use the schema from
  `methodology/SPINE_METHODOLOGY.md`.
- Raw chunks live in `raw/`, processed nodes in `nodes/` — keep the
  `U<n>` ↔ `KEDR_<n>` trailing-number pairing.
- Write Python with `newline='\n'` (see the CRLF protocol in the README).
- Update `CHANGELOG.md` under `Unreleased`.

Maintainers squash-merge into `main`. CI runs on every PR and on `v*` tags.
