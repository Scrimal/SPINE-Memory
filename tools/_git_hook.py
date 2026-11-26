#!/usr/bin/env python3
"""SPINE git hook — scaffold a CODE_MEMORY node from a merged PR.

Deterministic byproduct-filling: takes PR metadata and writes a node skeleton
with ``repo_ref`` / ``code_refs`` and a raw ``# SOURCE_BASE``. The agent (or a
later LLM pass) fills IMPULSE / SUMMARY / CLEANED_DATA, then critic + commit.

This is the anti-cold-start mechanism: memory fills itself as a side effect of
normal work, instead of requiring a manual "write a memory node" step.

Usage:
  python tools/_git_hook.py --kind postmortem --title "fix: auth timeout" \
      --repo /path/to/repo --commit a1b2c3d \
      --files src/auth/jwt.py migrations/0042_users.sql
"""

import argparse
import datetime
import os
import re

try:
    from spine_memory._node_io import find_spine_root
except ImportError:
    from _node_io import find_spine_root

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = find_spine_root()

KIND_DOMAIN = {
    'adr': 'Архитектура',
    'postmortem': 'Инциденты',
    'contract': 'Контракты',
    'gotcha': 'Грабли',
}
KIND_PREFIX = {
    'adr': 'ADR',
    'postmortem': 'PM',
    'contract': 'CTR',
    'gotcha': 'GOTCHA',
}


def next_id(nodes_dir, prefix):
    pat = re.compile(r'^%s_(\d+)' % re.escape(prefix))
    mx = 0
    if os.path.isdir(nodes_dir):
        for fn in os.listdir(nodes_dir):
            m = pat.match(fn.replace('.md', ''))
            if m:
                mx = max(mx, int(m.group(1)))
    return '%s_%03d' % (prefix, mx + 1)


def slugify(s):
    s = s.lower()
    s = re.sub(r'[^a-zа-яё0-9]+', '_', s)
    return s.strip('_')[:40]


def render(args):
    node_id = next_id(args.nodes, KIND_PREFIX[args.kind])
    today = datetime.date.today().isoformat()
    domain = KIND_DOMAIN[args.kind]

    anchors = [slugify(args.title), args.kind]
    if args.repo:
        anchors.append(slugify(os.path.basename(args.repo.rstrip('/\\'))))
    anchors = [a for a in anchors if a]

    lines = ['---']
    lines.append('id: %s' % node_id)
    lines.append('type: spine_node')
    lines.append('created: %s' % today)
    lines.append('tags: [code_memory, %s]' % args.kind)
    lines.append('domain: %s' % domain)
    lines.append('kind: %s' % args.kind)
    lines.append('status: active')
    if args.repo and args.commit:
        lines.append('repo_ref:')
        lines.append('  path: %s' % (args.repo_ref_path or ''))
        lines.append('  commit: %s' % args.commit)
    if args.files:
        lines.append('code_refs:')
        for f in args.files:
            lines.append('  - "%s"' % f)
    lines.append('search_anchors:')
    for a in anchors:
        lines.append('  - %s' % a)
    lines.append('---')
    lines.append('')
    lines.append('# IMPULSE')
    lines.append('TODO: две строки — суть решения/инцидента')
    lines.append('')
    lines.append('# SUMMARY')
    lines.append('TODO: 3-5 предложений')
    lines.append('')
    lines.append('# CLEANED_DATA')
    lines.append('TODO: сухие факты')
    lines.append('')
    lines.append('# IMPACT')
    lines.append('impact:')
    lines.append('  strategic_weight: 0.5')
    lines.append('  key_insight: |')
    lines.append('    TODO')
    lines.append('')
    lines.append('# SOURCE_BASE')
    lines.append('TITLE: %s' % args.title)
    if args.body:
        lines.append('')
        lines.append(args.body)
    if args.files:
        lines.append('')
        lines.append('FILES:')
        for f in args.files:
            lines.append('- %s' % f)
    lines.append('')
    lines.append('---')
    return node_id, '\n'.join(lines) + '\n'


def main():
    p = argparse.ArgumentParser(
        description='Scaffold a CODE_MEMORY node from a merged PR.')
    p.add_argument('--kind', required=True,
                   choices=['adr', 'postmortem', 'contract', 'gotcha'])
    p.add_argument('--title', required=True)
    p.add_argument('--body', default=None, help='PR body text')
    p.add_argument('--body-file', default=None, help='read PR body from file')
    p.add_argument('--repo', default=None, help='repo path (for slug anchor)')
    p.add_argument('--repo-ref-path', default=None,
                   help='primary repo path for repo_ref (e.g. src/auth/jwt.py)')
    p.add_argument('--commit', default=None, help='commit hash')
    p.add_argument('--files', nargs='*', default=None, help='changed files')
    p.add_argument('--nodes', default=os.path.join(ROOT, 'nodes'))
    p.add_argument('--out', default=None,
                   help='output dir (default: <nodes>/../temp)')
    args = p.parse_args()

    if args.body_file:
        with open(args.body_file, 'r', encoding='utf-8') as f:
            args.body = f.read().strip()

    node_id, text = render(args)

    out_dir = args.out or os.path.join(os.path.dirname(args.nodes), 'temp')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, node_id + '.md')
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print('scaffolded %s -> %s' % (node_id, out_path))


if __name__ == '__main__':
    main()
