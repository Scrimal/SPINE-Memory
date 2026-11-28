# Changelog

All notable changes to SPINE-Memory are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-11-28

### Added

- `[project.urls]` metadata (Homepage, Repository, Documentation, Issues, Changelog).
- Expanded PyPI classifiers (Python 3.9–3.13, OS Independent, MIT license).
- `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`.

### Fixed

- Verified README `~` escaping (single `~` throughout; no `~~` strikethrough).

## [0.2.0] - 2026-11-26

### Added

- Canonical node parser `tools/_node_io.py` — one reader/writer instead of six
  ad-hoc regex copies; `SOURCE_BASE` protection, safe `semantic_links` writes.
- Dev overlay: `CODE_MEMORY` (`kind`, `repo_ref`, `code_refs`, `status`),
  `code_index`, `spine_for_file`, `spine_preflight`, `_git_hook`.
- `spine` CLI: `init/index/wander/preflight/mcp/audit/crosslink/hook/daemon/benchmark/embed`.
- Packaging: `pyproject.toml`, zero-dependency core, `publish.yml` on `v*` tags.
- Demo corpus "Кедр-9": `KEDR_001..006` + `docs/longread.md`.

### Fixed

- Graph-root resolution (`find_spine_root`) for `pip install` outside the repo.
- PEP 639 license classifier conflict.
- `_build_index` writes JSON with `newline='\n'` (CRLF protocol).
