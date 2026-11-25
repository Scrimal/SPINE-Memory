#!/usr/bin/env python3
"""SPINE wanderer — обход графа по прямым и обратным связям.

By default walks semantic links only; --embed adds vector links (## EMBED_LINKS).

Запуск:
  python tools/_wander.py --from KEDR_001 --hops 2 --folder nodes
  python tools/_wander.py --from KEDR_001 --hops 2 --folder nodes --embed
  python tools/_wander.py --from KEDR_001 --hops 2 --folder nodes --back
"""

import argparse
import json
import os
import re
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _node_io

REVERSE_PATH = 'reverse_index.json'


def read_node(path):
    d = _node_io.read_node(path)
    if d is None:
        return {'id': os.path.basename(path).replace('.md', ''),
                'impulse': '', 'sem_links': [], 'embed_links': [], 'anchors': []}
    return {'id': d['id'], 'impulse': d['impulse'],
            'sem_links': d['semantic_links'], 'embed_links': d['embed_links'],
            'anchors': d['search_anchors']}


def load_index(folders):
    node_index, anchor_index = {}, {}
    for folder in folders:
        if not os.path.exists(folder):
            continue
        for f in sorted(os.listdir(folder)):
            if not f.endswith('.md'):
                continue
            data = read_node(os.path.join(folder, f))
            node_index[data['id']] = data
            for a in data['anchors']:
                anchor_index.setdefault(a, []).append(data['id'])
    return node_index, anchor_index


def load_reverse(include_embed=False):
    backlinks = {}
    if not os.path.exists(REVERSE_PATH):
        return backlinks
    with open(REVERSE_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    forward = dict(data.get('forward', {}))
    if include_embed:
        for src, targets in data.get('embed_forward', {}).items():
            forward.setdefault(src, []).extend(targets)
    for source, targets in forward.items():
        for target in targets:
            backlinks.setdefault(target, []).append(source)
    for k in backlinks:
        backlinks[k] = list(set(backlinks[k]))
    return backlinks


def wander(start, hops, node_index, anchor_index, backlinks=None,
           show_back=False, include_embed=False):
    if start in node_index:
        current = start
    elif start in anchor_index:
        current = anchor_index[start][0]
    else:
        print('Not found: ' + start)
        return

    visited = set()
    queue = [(current, 0)]

    while queue:
        nid, depth = queue.pop(0)
        if nid in visited or depth > hops:
            continue
        visited.add(nid)
        data = node_index.get(nid)
        if not data:
            continue

        links = list(data['sem_links'])
        if include_embed:
            links += data.get('embed_links', [])
        links = list(dict.fromkeys(links))

        imp = data['impulse'].replace('\n', ' ')[:100]
        indent = '  ' * depth

        real_links = [l for l in links if l in node_index]
        new_links = [l for l in real_links if l not in visited]

        print('%s%s: %s' % (indent, nid, imp))
        if new_links:
            print('%s  -> %s' % (indent, ', '.join(new_links[:3])))

        if show_back and backlinks and nid in backlinks:
            bl = backlinks[nid]
            back = ' <- [' + ', '.join(bl[:5]) + ']'
            if len(bl) > 5:
                back += ' +%d more' % (len(bl) - 5)
            print('%s  %s' % (indent, back))

        for link in links:
            if link not in visited and link in node_index:
                queue.append((link, depth + 1))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--from', dest='start', required=True)
    p.add_argument('--hops', type=int, default=3)
    p.add_argument('--folder', action='append', default=None,
                   help='folder with nodes (repeatable)')
    p.add_argument('--back', action='store_true', help='show backlinks')
    p.add_argument('--embed', action='store_true',
                   help='also walk embed links (## EMBED_LINKS)')
    args = p.parse_args()

    folders = args.folder or ['nodes']
    ni, ai = load_index(folders)
    bl = load_reverse(args.embed) if args.back else None

    extra = (' back' if args.back else '') + (' embed' if args.embed else '')
    print('WANDERER | %s | hops: %d | index: %d nodes%s' % (
        args.start, args.hops, len(ni), extra))
    print()
    wander(args.start, args.hops, ni, ai, bl, args.back, args.embed)


if __name__ == '__main__':
    main()
