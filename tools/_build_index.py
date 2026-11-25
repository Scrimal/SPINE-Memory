#!/usr/bin/env python3
"""SPINE index builder — compile reverse_index.json and refresh anchor_dump.json.

Reads nodes/*.md and:
  1. builds forward semantic links  {node_id: [target_ids]} (YAML semantic_links)
  2. builds embed links             {node_id: [target_ids]} (body ## EMBED_LINKS)
  3. inverts both → reverse_index.json:
       forward / reverse / embed_forward / embed_reverse
  4. refreshes anchors/anchor_dump.json (canon)

Usage:
  python tools/_build_index.py
"""

import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import _node_io
NODES_DIR = os.path.join(BASE, '..', 'nodes')
ANCHOR_DUMP = os.path.join(BASE, '..', 'anchors', 'anchor_dump.json')
REVERSE_INDEX = os.path.join(BASE, '..', 'reverse_index.json')


def read_node(path):
    """Read a node via the canonical _node_io parser.

    Returns (nid, semantic_links, embed_links, anchors, code_refs).
    """
    d = _node_io.read_node(path)
    if d is None:
        return None, [], [], [], []
    return (d['id'], d['semantic_links'], d['embed_links'],
            d['search_anchors'], d['code_refs'])


def _code_ref_path(ref):
    """Extract the file path from a code_ref like 'src/a.py::fn@commit'."""
    return ref.split('::')[0].split('@')[0].strip()


def invert(forward):
    rev = {}
    for src, targets in forward.items():
        for t in targets:
            rev.setdefault(t, []).append(src)
    for k in rev:
        rev[k] = sorted(set(rev[k]))
    return rev


def main():
    forward, embed_forward, anchor_nodes, code_index = {}, {}, {}, {}
    if os.path.isdir(NODES_DIR):
        for fn in sorted(os.listdir(NODES_DIR)):
            if not fn.endswith('.md'):
                continue
            nid, sem, embed, anchors, code_refs = read_node(os.path.join(NODES_DIR, fn))
            forward[nid] = sem
            embed_forward[nid] = embed
            for a in anchors:
                anchor_nodes.setdefault(a, []).append(nid)
            for ref in code_refs:
                p = _code_ref_path(ref)
                if p:
                    code_index.setdefault(p, []).append(nid)

    for p in code_index:
        code_index[p] = sorted(set(code_index[p]))

    reverse = invert(forward)
    embed_reverse = invert(embed_forward)

    with open(REVERSE_INDEX, 'w', encoding='utf-8', newline='\n') as f:
        json.dump({
            'forward': forward,
            'reverse': reverse,
            'embed_forward': embed_forward,
            'embed_reverse': embed_reverse,
            'code_index': code_index,
        }, f, ensure_ascii=False, indent=2)

    canon = {}
    if os.path.exists(ANCHOR_DUMP):
        with open(ANCHOR_DUMP, 'r', encoding='utf-8') as f:
            canon = json.load(f)
    for a, nids in anchor_nodes.items():
        canon.setdefault(a, []).extend(nids)
    for a in canon:
        canon[a] = sorted(set(canon[a]))
    with open(ANCHOR_DUMP, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(canon, f, ensure_ascii=False, indent=2)

    print('reverse_index.json: semantic %d nodes / embed %d nodes' % (
        len(forward), len(embed_forward)))
    print('anchor_dump.json: %d anchors' % len(canon))


if __name__ == '__main__':
    main()
