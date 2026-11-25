#!/usr/bin/env python3
"""SPINE crosslink — generate semantic links between nodes.

Rules: a link is created inside the same constellation OR on overlap of
>=2 anchors. Per-node link limit is controlled by --max (default 1).

Links are written into the YAML frontmatter `semantic_links:` list so that
_wander.py and any v2.1-compliant reader can see them.

Usage:
  python tools/_crosslink.py --folder nodes           # dry run
  python tools/_crosslink.py --folder nodes --apply    # apply
"""

import argparse
import os
import re
import sys
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _node_io

MIN_ANCHOR_OVERLAP = 2


def read_node(path):
    d = _node_io.read_node(path)
    if d is None:
        return None
    return {
        'path': path,
        'id': d['id'],
        'constellation': d['constellation'],
        'anchors': d['search_anchors'],
        'existing_links': set(d['semantic_links']),
    }


def load_all(folders):
    nodes = {}
    for folder in folders:
        if not os.path.exists(folder):
            continue
        for fn in sorted(os.listdir(folder)):
            if not fn.endswith('.md'):
                continue
            data = read_node(os.path.join(folder, fn))
            if data and data['id']:
                nodes[data['id']] = data
    return nodes


def find_pairs(nodes):
    pairs = []
    ids = list(nodes.keys())

    const_groups = defaultdict(list)
    for nid, nd in nodes.items():
        if nd['constellation']:
            const_groups[nd['constellation']].append(nid)

    const_linked = set()
    for const, members in const_groups.items():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                pairs.append((members[i], members[j], f'const:{const}'))
                const_linked.add(tuple(sorted([members[i], members[j]])))

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            key = tuple(sorted([ids[i], ids[j]]))
            if key in const_linked:
                continue
            overlap = set(nodes[ids[i]]['anchors']) & set(nodes[ids[j]]['anchors'])
            if len(overlap) >= MIN_ANCHOR_OVERLAP:
                pairs.append((ids[i], ids[j], f'anchors:{",".join(sorted(overlap)[:3])}'))

    seen = set()
    unique = []
    for a, b, reason in pairs:
        key = tuple(sorted([a, b]))
        if key not in seen:
            seen.add(key)
            unique.append((a, b, reason))
    return unique


def apply_link(nid, target, reason, nodes, max_links):
    nd = nodes.get(nid)
    if not nd:
        return False
    if target in nd['existing_links']:
        return False
    if len(nd['existing_links']) >= max_links:
        return False
    return _node_io.add_semantic_link(nd['path'], target, reason)


def main():
    p = argparse.ArgumentParser(description='Generate semantic links between SPINE nodes.')
    p.add_argument('--folder', action='append', default=None,
                   help='folder with nodes (repeatable)')
    p.add_argument('--apply', action='store_true', help='write links to files')
    p.add_argument('--max', type=int, default=3, help='max links per node')
    args = p.parse_args()

    folders = args.folder or ['nodes']

    nodes = load_all(folders)
    pairs = find_pairs(nodes)

    node_link_count = defaultdict(int)
    for nid in nodes:
        node_link_count[nid] = len(nodes[nid]['existing_links'])

    filtered = []
    for a, b, reason in pairs:
        if node_link_count[a] < args.max and node_link_count[b] < args.max:
            filtered.append((a, b, reason))
            node_link_count[a] += 1
            node_link_count[b] += 1

    print(f'CROSSLINK | nodes: {len(nodes)} | candidates: {len(pairs)} | filtered: {len(filtered)}')
    print(f'rules: max {args.max} links/node, min {MIN_ANCHOR_OVERLAP} anchor overlap\n')

    if args.apply:
        applied = 0
        for a, b, reason in filtered:
            r1 = apply_link(a, b, reason, nodes, args.max)
            r2 = apply_link(b, a, reason, nodes, args.max)
            if r1 or r2:
                applied += 1
                print(f'  {a} <-> {b}  [{reason}]')
        print(f'\napplied: {applied} links')
    else:
        print('DRY RUN (use --apply). Samples:')
        for a, b, reason in filtered[:20]:
            print(f'  {a} <-> {b}  [{reason}]')
        if len(filtered) > 20:
            print(f'  ... and {len(filtered) - 20} more')


if __name__ == '__main__':
    main()
