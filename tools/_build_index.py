#!/usr/bin/env python3
"""SPINE index builder — compile reverse_index.json and refresh anchor_dump.json.

Reads nodes/*.md and:
  1. builds forward semantic links  {node_id: [target_ids]}
  2. inverts them into reverse_index.json
  3. refreshes anchors/anchor_dump.json with anchors found in nodes (canon)

Usage:
  python tools/_build_index.py
"""

import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
NODES_DIR = os.path.join(BASE, '..', 'nodes')
ANCHOR_DUMP = os.path.join(BASE, '..', 'anchors', 'anchor_dump.json')
REVERSE_INDEX = os.path.join(BASE, '..', 'reverse_index.json')


def read_frontmatter(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    parts = content.split('---', 2)
    if len(parts) < 3:
        return None, [], []
    fm = parts[1]

    m = re.search(r'^id:\s*(\S+)', fm, re.MULTILINE)
    nid = m.group(1) if m else os.path.basename(path).replace('.md', '')

    sem = []
    m = re.search(r'^semantic_links:\n((?:\s+-\s.*\n?)*)', fm, re.MULTILINE)
    if m:
        sem = re.findall(r'\[\[([^\]]+)\]\]', m.group(1))

    anchors = []
    m = re.search(r'^search_anchors:\n((?:\s+-\s.*\n?)*)', fm, re.MULTILINE)
    if m:
        anchors = [a.strip().split('#')[0].strip()
                   for a in re.findall(r'-\s*([^\s#]+)', m.group(1))]
    return nid, sem, anchors


def main():
    forward = {}
    anchor_nodes = {}
    if os.path.isdir(NODES_DIR):
        for fn in sorted(os.listdir(NODES_DIR)):
            if not fn.endswith('.md'):
                continue
            nid, sem, anchors = read_frontmatter(os.path.join(NODES_DIR, fn))
            forward[nid] = sem
            for a in anchors:
                anchor_nodes.setdefault(a, []).append(nid)

    # Reverse index
    reverse = {}
    for src, targets in forward.items():
        for t in targets:
            reverse.setdefault(t, []).append(src)
    for k in reverse:
        reverse[k] = sorted(set(reverse[k]))

    with open(REVERSE_INDEX, 'w', encoding='utf-8') as f:
        json.dump({'forward': forward, 'reverse': reverse}, f,
                  ensure_ascii=False, indent=2)

    # Refresh anchor canon (new format: {anchor: [node_ids]})
    canon = {}
    if os.path.exists(ANCHOR_DUMP):
        with open(ANCHOR_DUMP, 'r', encoding='utf-8') as f:
            canon = json.load(f)
    for a, nids in anchor_nodes.items():
        canon.setdefault(a, []).extend(nids)
    for a in canon:
        canon[a] = sorted(set(canon[a]))

    with open(ANCHOR_DUMP, 'w', encoding='utf-8') as f:
        json.dump(canon, f, ensure_ascii=False, indent=2)

    print('reverse_index.json: %d nodes -> %d reverse entries' % (
        len(forward), len(reverse)))
    print('anchor_dump.json: %d anchors' % len(canon))


if __name__ == '__main__':
    main()
