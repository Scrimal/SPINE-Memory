#!/usr/bin/env python3
"""SPINE preflight — proactive context radar.

Given a set of changed files (from ``git diff`` or explicit ``--files``), find
all CODE_MEMORY nodes (ADR / post-mortem / gotcha) linked to those files via
``code_refs`` in reverse_index.json. This is the "show me what I might break
before I break it" tool: it returns the impulse of every architectural
decision, past incident or gotcha touching the files you are about to change.

Usage:
  python tools/spine_preflight.py --repo /path/to/repo
  python tools/spine_preflight.py --files src/auth/jwt.py migrations/0042.sql
"""

import argparse
import json
import os
import subprocess
import sys

try:
    from spine_memory._node_io import read_node, find_spine_root
except ImportError:
    from _node_io import read_node, find_spine_root

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = find_spine_root()


def load_code_index(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('code_index', {})


def load_node_impulses(nodes_dir):
    idx = {}
    if not os.path.isdir(nodes_dir):
        return idx
    for fn in sorted(os.listdir(nodes_dir)):
        if not fn.endswith('.md'):
            continue
        d = read_node(os.path.join(nodes_dir, fn))
        if d:
            idx[d['id']] = d['impulse'] or d['summary'] or ''
    return idx


def match_files(code_index, files):
    """Return {filepath: [node_ids]} for nodes whose code_refs match files."""
    out = {}
    for fp in files:
        hits = set()
        for ref_path, nids in code_index.items():
            if fp == ref_path or fp.endswith(ref_path) or ref_path.endswith(fp):
                hits.update(nids)
        if hits:
            out[fp] = sorted(hits)
    return out


def main():
    p = argparse.ArgumentParser(description='SPINE preflight: memory for changed files')
    p.add_argument('--repo', default=None, help='git repo to diff')
    p.add_argument('--files', nargs='*', default=None, help='explicit file list')
    p.add_argument('--index', default=os.path.join(ROOT, 'reverse_index.json'))
    p.add_argument('--nodes', default=os.path.join(ROOT, 'nodes'))
    args = p.parse_args()

    files = list(args.files) if args.files else []
    if args.repo:
        r = subprocess.run(['git', '-C', args.repo, 'diff', '--name-only'],
                           capture_output=True, text=True)
        if r.returncode == 0:
            files = [l for l in r.stdout.splitlines() if l.strip()]
        else:
            print('git diff failed:', r.stderr.strip(), file=sys.stderr)

    if not files:
        print('no changed files')
        return

    if not os.path.exists(args.index):
        print('index not found:', args.index)
        return

    code_index = load_code_index(args.index)
    matched = match_files(code_index, files)
    impulses = load_node_impulses(args.nodes)

    if not matched:
        print('no SPINE memory for changed files')
        return

    for fp, nids in matched.items():
        print('## %s' % fp)
        for nid in nids:
            imp = (impulses.get(nid, '') or '').replace('\n', ' ')[:120]
            print('- %s: %s' % (nid, imp or '—'))


if __name__ == '__main__':
    main()
