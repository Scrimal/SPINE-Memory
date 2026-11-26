---
name: spine-memory
description: Manage, ingest, validate, and traverse a hierarchical Markdown/YAML graph memory (SPINE v2.1) with progressive disclosure and zero-token deterministic guardrails.
---

# SPINE Memory Agent Skill

Use this skill to store, ingest, organize, audit, or retrieve long-term context
from a SPINE Markdown/YAML knowledge graph.

## Core Principles

1. **Progressive Disclosure.** Follow the retrieval funnel
   (`Domain/Constellation` → `IMPULSE` → `SUMMARY` → `CLEANED_DATA` →
   `SOURCE_BASE`) without loading full verbatim sections upfront. Never load
   `SOURCE_BASE` during routing or synthesis — it is the lossless basement for
   deep drill-down and fine-tuning.
2. **Staging Discipline.** Draft new nodes in a temporary staging folder,
   validate them via `tools/_critic_check.sh`, fix issues, and commit atomically.
3. **Context Compaction.** Compact working context into short snapshots every
   5 nodes during batch ingestion.

## Node Schema (v2.1)

- **YAML frontmatter:** `id`, `type: spine_node`, `domain`, `hub`,
  `constellation`, `vectors` (`domain::vector` with a `#` comment),
  `search_anchors` (3–5 lowercase `snake_case`, no leading digits),
  `chronology` (`roots`/`after`), `semantic_links`.
- **Body sections (fixed order):**
  - `# IMPULSE` — 1–2 lines
  - `# SUMMARY` — 3–5 sentences
  - `# CLEANED_DATA` — ~25 lines of facts
  - `# IMPACT` — `strategic_weight` + `key_insight`
  - `# SOURCE_BASE` — ≥70% of the raw source by bytes

## Tools (run from repo root)

```bash
# validate nodes
bash tools/_critic_check.sh nodes raw anchors/anchor_dump.json

# validate anchors against canon
python tools/_check_anchors.py nodes/<ID>.md --dump anchors/anchor_dump.json --quiet

# traverse the graph
python tools/_wander.py --from <ID> --hops 2 --folder nodes

# generate semantic links (dry run / apply)
python tools/_crosslink.py --folder nodes [--apply]

# global quality audit
python tools/_quality_audit.py --nodes nodes --raw raw

# rebuild reverse_index.json + refresh anchor canon
python tools/_build_index.py
```

## Naming Convention

Raw chunks live in `raw/U<number>.md`. Processed nodes live in
`nodes/<ID>.md`. The critic matches `nodes/KEDR_001.md` to `raw/U001.md` by the
trailing number — keep this pairing when adding new domains.

## Dev Overlay: memory around code (not code itself)

SPINE does **not** index source code — LSP / Tree-sitter / `ripgrep` own that.
SPINE stores the **intent**: why a decision was made, what broke and how it was
fixed, what traps exist.

### Routing rule (always)

- question about a symbol / path / line → `ripgrep` / LSP first
- question about why / decision / history → SPINE first
- both → SPINE for context, `ripgrep` for ground truth

### CODE_MEMORY node (one type, four kinds)

```yaml
kind: adr | postmortem | gotcha | contract
repo_ref: {path, commit, lines}      # pointer to code, NOT a copy (Git is the store)
code_refs: ["src/a.py::fn@abc123", ...]  # exact file bindings
status: active | superseded | historical   # facts don't decay, they get superseded
```

- `adr` — architectural decision (why X, alternatives, tradeoffs)
- `postmortem` — incident investigation (`roots -> after` works perfectly)
- `gotcha` — repo trap (build order, SDK bug, deploy quirk)
- `contract` — API schema/event shape (store as "as-of" facts; rots fastest)

### Dev tools

- `spine_for_file(filepath)` — ADR/post-mortem/gotcha linked to a code file
- `spine_preflight --files ...` — what you might break before you change it
- `_git_hook.py --kind ...` — scaffold a node from a merged PR (byproduct filling)
