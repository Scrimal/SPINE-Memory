#!/usr/bin/env python3
"""SPINE CLI — single entry point for the SPINE-Memory toolchain.

Commands:
  spine init [--preset general|dev] [--dir .]   scaffold a .spine/ graph
  spine index                                    rebuild reverse_index.json
  spine wander --from ID --hops N                traverse the graph
  spine preflight --files ...                    memory for changed code files
  spine mcp                                      start the MCP server

All non-init commands forward to the sibling tool scripts, so they work both
from a source checkout and from a pip-installed package.
"""

import argparse
import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))

GENERAL_SKILL = """\
# SPINE Memory Skill (general)

Progressive disclosure: Domain/Constellation -> IMPULSE -> SUMMARY ->
CLEANED_DATA -> SOURCE_BASE. Never load SOURCE_BASE during routing/synthesis.

Node schema (v2.1): YAML frontmatter (id, type: spine_node, domain, hub,
constellation, vectors, search_anchors, chronology, semantic_links) + body
sections in fixed order: # IMPULSE, # SUMMARY, # CLEANED_DATA, # IMPACT,
# SOURCE_BASE.
"""

DEV_SKILL = """\
# SPINE Memory Skill (dev overlay)

SPINE does NOT index source code — LSP / Tree-sitter / ripgrep own that.
SPINE stores intent: why a decision was made, what broke, what traps exist.

Routing rule:
  - symbol / path / line  -> ripgrep / LSP first
  - why / decision / history -> SPINE first
  - both -> SPINE for context, ripgrep for ground truth

CODE_MEMORY node: one type, four kinds (adr | postmortem | gotcha | contract),
plus repo_ref {path, commit, lines}, code_refs ["path::symbol@commit"],
status: active | superseded | historical.
"""

GENERAL_TEMPLATE = """\
---
id: NOTE_001
type: spine_node
domain: Заметки
search_anchors:
  - якорь_один
  - якорь_два
  - якорь_три
---

# IMPULSE
TODO: две строки

# SUMMARY
TODO: 3-5 предложений

# CLEANED_DATA
TODO: факты

# IMPACT
impact:
  strategic_weight: 0.5
  key_insight: |
    TODO

# SOURCE_BASE
TODO: сырой источник
"""

DEV_TEMPLATE = """\
---
id: ADR_001
type: spine_node
domain: Архитектура
kind: adr
status: active
repo_ref:
  path: src/example.py
  commit: HEAD
  lines: ""
code_refs:
  - "src/example.py"
search_anchors:
  - пример_решения
  - архитектурный_выбор
  - компромисс
---

# IMPULSE
TODO: две строки — суть решения

# SUMMARY
TODO: 3-5 предложений — почему, альтернативы, компромисс

# CLEANED_DATA
TODO: сухие факты

# IMPACT
impact:
  strategic_weight: 0.5
  key_insight: |
    TODO

# SOURCE_BASE
TODO: обсуждение / PR body / разбор инцидента
"""

EMPTY_INDEX = {
    'forward': {}, 'reverse': {},
    'embed_forward': {}, 'embed_reverse': {},
    'code_index': {},
}


def cmd_init(args):
    target = args.dir or '.'
    spine_dir = os.path.join(target, '.spine')
    dirs = ['nodes', 'raw', 'anchors', 'thoughts']
    for d in dirs:
        os.makedirs(os.path.join(spine_dir, d), exist_ok=True)

    skill = DEV_SKILL if args.preset == 'dev' else GENERAL_SKILL
    template = DEV_TEMPLATE if args.preset == 'dev' else GENERAL_TEMPLATE

    with open(os.path.join(spine_dir, 'SKILL.md'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(skill)
    tpl_name = '_TEMPLATE_dev.md' if args.preset == 'dev' else '_TEMPLATE.md'
    with open(os.path.join(spine_dir, 'nodes', tpl_name), 'w', encoding='utf-8', newline='\n') as f:
        f.write(template)
    with open(os.path.join(spine_dir, 'reverse_index.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(EMPTY_INDEX, f, ensure_ascii=False, indent=2)
    with open(os.path.join(spine_dir, 'anchors', 'anchor_dump.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

    print('SPINE graph scaffolded in %s (preset: %s)' % (spine_dir, args.preset))


SCRIPT_MAP = {
    'index': '_build_index.py',
    'wander': '_wander.py',
    'preflight': 'spine_preflight.py',
    'mcp': 'mcp_server.py',
    'audit': '_quality_audit.py',
    'crosslink': '_crosslink.py',
    'hook': '_git_hook.py',
    'daemon': 'night_daemon.py',
    'benchmark': 'benchmark_tokens.py',
    'embed': '_embed_links.py',
}


def main():
    if len(sys.argv) < 2:
        print('usage: spine <init|index|wander|preflight|mcp|audit|crosslink|hook|daemon|benchmark|embed> [args]')
        return

    cmd = sys.argv[1]
    rest = sys.argv[2:]

    if cmd == 'init':
        p = argparse.ArgumentParser(prog='spine init')
        p.add_argument('--preset', choices=['general', 'dev'], default='general')
        p.add_argument('--dir', default='.')
        cmd_init(p.parse_args(rest))
        return

    script = SCRIPT_MAP.get(cmd)
    if not script:
        print('unknown command: %s' % cmd)
        print('usage: spine <init|index|wander|preflight|mcp|audit|crosslink|hook|daemon|benchmark|embed> [args]')
        return

    subprocess.run([sys.executable, os.path.join(BASE, script)] + rest)


if __name__ == '__main__':
    main()
