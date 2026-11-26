# SPINE: Long-Term Memory Graph Methodology

Version 1.0 (public)

SPINE is a methodology for structuring an agent's long-term memory as a
directed graph. It is neither a document database nor a flat vector store:
each record is a neuron-node with coordinates in a space of meaning.

The architecture's goal is navigation, scalability, and reproducibility as the
store grows from hundreds to tens of thousands of nodes without losing
connectivity.

---

## 1. Core principles

| Principle | Purpose |
|-----------|---------|
| Tiered navigation | domain → constellation → node (three entry levels) |
| Dual topology | chronology (`roots`/`after`) + semantics (`semantic_links`) |
| Compression with raw preservation | fast layer (impulse/summary) + full layer (source_base) |
| Anchors | consistent phrasing matters more than uniqueness |
| Deterministic validation | every node passes a script critic before entering the graph |

---

## 2. Three navigation tiers

| Tier | Unit | Size | Role |
|------|------|------|------|
| Domain | Galaxy | 50–500 nodes | broad knowledge area |
| Constellation | Thematic cluster | 5–20 nodes | connected group |
| Node | Neuron | 1 record | atomic memory unit |

Domains are top-level categories. Their set is domain-specific and fixed at
graph initialization. Example from the «Kedr-9» demo project:

| Domain | Content |
|--------|---------|
| Выживание (Survival) | physical state, resources, basic needs |
| Железо (Hardware) | equipment, tools, machinery |
| Карта (Map) | navigation, terrain, external observations |
| Тайны_Груза (Cargo Mysteries) | plot-level open questions |
| Психология (Psychology) | identity, memory, cognitive state |
| Связь (Communication) | protocols, memory architecture |

---

## 3. Node structure (format v2.1)

Each node is a Markdown file with a YAML frontmatter (metadata) and a body
(content layers).

### 3.1 YAML frontmatter

```yaml
---
id: KEDR_001                 # unique identifier
type: spine_node             # record type
created: 2026-11-23          # creation date (ISO)
tags: [spine_node, demo]     # flat tags
domain: Связь                # domain (see section 2)
hub: "[[Кедр_Связь]]"        # primary hub node (Obsidian link)
constellation: Кедр-9 Expedition
vectors:                     # directions, not tags
  - "связь::трёхслойный_архив"  # comment required
search_anchors:              # 3–5 anchors, snake_case
  - трёхслойный_архив
  - обходчик_графа
chronology:                  # chronological topology
  roots: "[[U001]]"          # where the node came from
  after: "[[KEDR_002]]:continuation"  # where it leads, with link type
semantic_links:              # semantic relations
  - "[[KEDR_002]]::продолжение"
---
```

Frontmatter requirements:

- `vectors` — strictly `domain::vector` with a `#` comment. A direction along a
  meaning axis, not a tag.
- `search_anchors` — 3–5 items, `snake_case`, only `a-z`, `а-я`, `0-9`, `_`,
  no capitals, must not start with a digit, 2–5 tokens.
- `[[Node]]` links inside YAML strings must be quoted (`"[[Node]]"`), otherwise
  the metadata parser cannot read them.

### 3.2 Node body (fixed section order)

```
# IMPULSE        — 1–2 lines, compressed signal for fast filtering
# SUMMARY        — 3–5 sentences, dry concentrate
# CLEANED_DATA   — ~25 lines, structured facts
# IMPACT         — strategic_weight + key_insight
# SOURCE_BASE    — ≥70% of the source text, unshortened
```

| Section | Purpose | Rule |
|---------|---------|------|
| `# IMPULSE` | the node's «scent», chemotaxis | 1–2 lines, no dates/timestamps |
| `# SUMMARY` | concentrated essence | 3–5 sentences |
| `# CLEANED_DATA` | facts scannable at a glance | ~25 lines, shorter than SOURCE_BASE |
| `# IMPACT` | node weight and takeaway | `strategic_weight: 0.0–1.0` + `key_insight` |
| `# SOURCE_BASE` | full source for fine-tuning | ≥70% of raw by bytes |

Invariant: `CLEANED_DATA` is always shorter than `SOURCE_BASE`. The concentrate
serves navigation; the basement serves depth. If the concentrate is longer than
the raw source, the node is broken.

### 3.3 Dev overlay (CODE_MEMORY, optional)

For "memory around code" — architecture decisions, post-mortems, gotchas,
contracts — add optional frontmatter fields. SPINE does not index source code:
LSP / Tree-sitter / `ripgrep` own that. SPINE stores *why*.

```yaml
kind: adr | postmortem | gotcha | contract   # one of four kinds
repo_ref:                                     # pointer to Git, not a copy
  path: src/auth/jwt.py
  commit: a1b2c3d
  lines: "L45-L120"
code_refs:                                    # exact file bindings
  - "src/auth/jwt.py::verify_token@a1b2c3d"
  - "migrations/0042_users.sql"
status: active | superseded | historical      # facts don't decay; they get superseded
```

- `code_refs` feeds the reverse index (`code_index`) and powers
  `spine_for_file(filepath)` / `spine_preflight`.
- `status` replaces `decay_factor` for code nodes: a bugfix post-mortem does not
  become less true with time — it becomes historical. Whether it still applies
  *now* is answered by the repository (ripgrep/LSP), never by SPINE.
- `SOURCE_BASE` may be short for code nodes; the raw PR description / incident
  discussion is enough — the source itself lives in Git.

---

## 4. Links

### 4.1 Chronology

`chronology.roots` / `chronology.after` form the linear memory spine. Link types
(`:continuation`, `:genesis`, `:core`, `:origins`, `:contrast`, `:goal`,
`:continuation`) are written after `::`.

### 4.2 Semantic links

`semantic_links` are associative edges between nodes. They are built three ways:

1. manually (a deliberate relation with a type);
2. by anchor overlap (≥2 shared anchors) — the `_crosslink.py` script;
3. by embedding proximity (phase 3, threshold 0.88).

### 4.3 Reverse index

YAML links are unidirectional. The reverse index (`reverse_index.json`) is
computed at graph compilation and enables bidirectional navigation without
duplicating data in nodes.

---

## 5. Anchors (search_anchors)

Anchors are normalized key phrases for instant lookup without opening a node.
Rules:

- **Consistency over uniqueness.** The same anchor across nodes is a link, not a
  bug.
- **One formulation.** Do not spawn synonyms (`выравнивание_по_л` stays the same
  everywhere, never `выровняли_по_букве_л`).
- **Terms stay untranslated.** Proper nouns keep their original form.
- **People's names go into the node body, not into anchors.**
- **2–3 recurring + 1–2 unique** per node (3–5 total).

Validation: `_check_anchors.py` verifies format and absence of duplicates
against the canon in `anchors/anchor_dump.json`.

---

## 6. Record processing lifecycle

One record = one full cycle:

1. **Segmentation.** The raw stream is cut deterministically into fixed-size
   chunks (e.g. 5,000 chars).
2. **Impulse.** Write 1–2 lines — the compressed signal.
3. **Summary.** 3–5 sentences of concentrate.
4. **Cleaned data.** ~25 lines of facts.
5. **Impact.** `strategic_weight` + `key_insight`.
6. **Basement.** Full source text (≥70% of raw).
7. **Validation.** Run `_critic_check.sh` until a clean `PASS`.
8. **Linking.** `_crosslink.py` + reverse index.

Forbidden: batch processing without validation, shrinking `SOURCE_BASE` below
threshold, skipping nodes during numbering (chronology matters more than speed).

### 6.1 Staging: Temp → Critic → Commit

Batch processing is built around a temporary buffer and a deterministic critic
so that raw or invalid nodes never pollute the production graph:

1. **Temp Staging** — a node draft is written to a `TEMP` buffer, not to the
   production base.
2. **Zero-Token Critic** — `_critic_check.sh` runs on the draft (token-free:
   bash/Python, no LLM).
3. **Bounded Discretion** — the agent resolves boundary cases on its own (a
   short source below the line limit, a decimal point mistaken for a sentence
   terminator) without looping in self-criticism.
4. **Atomic Commit** — only a valid node enters the graph.
5. **Context Compaction** — every 5 nodes the heavy context is compacted into
   lightweight snapshots (impulse/summary), sustaining **40+ nodes (500k+
   tokens) per session** without degradation at **~$0.01/node**.

---

## 7. Tools

All utilities live in `tools/` and run from the repository root.

| Tool | Purpose |
|------|---------|
| `_critic_check.sh` | auto-audit: impulse ≤2 lines, summary ≤7 sentences, source_base ≥70%, vectors with `#` |
| `_check_anchors.py` | anchor validation against `anchors/anchor_dump.json` |
| `_crosslink.py` | smart links: constellations + anchor overlap (≥2), per-node limit |
| `_wander.py` | graph traversal via forward and backlinks |
| `_quality_audit.py` | global audit: metrics, source/raw ratio, duplicate synonyms |

Quick test after build:

```bash
bash tools/_critic_check.sh nodes raw
python tools/_check_anchors.py nodes/KEDR_001.md --dump anchors/anchor_dump.json --quiet
python tools/_wander.py --from KEDR_001 --hops 2 --folder nodes
```

---

## 8. Quality criteria (PASS)

A node is valid when:

- IMPULSE ≤ 2 lines;
- SUMMARY ≤ 5 sentences (tolerance up to 7 in the legacy dot counter);
- SOURCE_BASE ≥ 70% of the raw chunk by bytes;
- search_anchors: 3–5 items, snake_case, no duplicates;
- vectors: each with a `#` comment;
- YAML: `[[...]]` links quoted;
- chronology: `after` with a link type (`:`).

---

## 9. Scaling

| Scale | Strategy |
|-------|----------|
| ~100 nodes | manual traversal, impulse navigation |
| ~1,000 nodes | constellations + reverse index, hot/cold priorities |
| ~10,000 nodes | embedding axes (semantic gravity), autonomous walker daemon |

Access frequency raises a node's «brightness» (Hebbian learning); dormant nodes
cool down. Implemented via `access_count` / `last_accessed` fields.

---

## 10. Philosophical basis (brief)

The graph is not an archive of facts but a memory substrate. A biological brain
rewrites memories on every recall; SPINE does the same, but with a backup in
`SOURCE_BASE` and a rollback button. An agent's identity is the topology of its
links, not a set of documents.
