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

MIN_ANCHOR_OVERLAP = 2


def read_node(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    parts = content.split('---', 2)
    if len(parts) < 3:
        return None
    fm_text = parts[1]

    data = {
        'path': path,
        'id': None,
        'constellation': None,
        'anchors': [],
        'existing_links': set(),
    }

    m = re.search(r'^id:\s*(\S+)', fm_text, re.MULTILINE)
    if m:
        data['id'] = m.group(1)

    m = re.search(r'^constellation:\s*(.+)', fm_text, re.MULTILINE)
    if m:
        data['constellation'] = m.group(1).strip().strip('"')

    in_anchors = False
    for line in fm_text.split('\n'):
        s = line.strip()
        if s.startswith('search_anchors:'):
            in_anchors = True
            continue
        if in_anchors:
            if s.startswith('-'):
                a = s.lstrip('- ').split('#')[0].strip()
                if a:
                    data['anchors'].append(a)
            elif s and not s.startswith('#'):
                in_anchors = False

    in_links = False
    for line in fm_text.split('\n'):
        s = line.strip()
        if s.startswith('semantic_links:'):
            in_links = True
            continue
        if in_links:
            if s.startswith('-'):
                m2 = re.search(r'\[\[([^\]]+)\]\]', line)
                if m2:
                    data['existing_links'].add(m2.group(1))
            elif s and not s.startswith('#'):
                in_links = False

    # Backward compatibility: legacy links in the body section.
    body = parts[2]
    if '## SEMANTIC_LINKS' in body:
        sem_body = body.split('## SEMANTIC_LINKS')[1].split('##')[0]
        for m2 in re.finditer(r'\[\[([^\]]+)\]\]', sem_body):
            data['existing_links'].add(m2.group(1))

    return data


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

    path = nd['path']
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    parts = content.split('---', 2)
    if len(parts) < 3:
        return False
    fm = parts[1]
    body = parts[2]

    new_link = f'  - "[[{target}]]::{reason}"'
    if 'semantic_links:' in fm:
        fm_new = fm.replace('semantic_links:', 'semantic_links:\n' + new_link, 1)
    else:
        fm_new = fm.rstrip() + '\nsemantic_links:\n' + new_link + '\n'

    new_content = '---' + fm_new + '---' + body
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    return True


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
