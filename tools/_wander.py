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

REVERSE_PATH = 'reverse_index.json'


def extract_section(content, name):
    lines = content.split('\n')
    result = []
    inside = False
    for line in lines:
        s = line.strip()
        if not inside and s == name:
            inside = True
            continue
        if inside:
            if (s.startswith('# ') and s != name) or s == '---':
                break
            result.append(line)
    return '\n'.join(result).strip()


def read_node(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    fm = {}
    if fm_match:
        for line in fm_match.group(1).split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('#') and not line.startswith('-'):
                k, v = line.split(':', 1)
                fm[k.strip()] = v.strip().strip('"')
    nid = fm.get('id', os.path.basename(path).replace('.md', ''))

    imp = extract_section(content, '# IMPULSE')
    if not imp:
        imp_match = re.search(r'impulse:\s*[|>]\n((?:  .*\n?)*)', content)
        imp = imp_match.group(1).strip() if imp_match else ''

    sem_section = re.search(r'semantic_links:\n((?:\s+-\s.*\n?)*)', content)
    if not sem_section:
        sem_section = re.search(r'## SEMANTIC_LINKS\n((?:- .*\n?)*)', content)
    sem_links = re.findall(r'\[\[(.+?)\]\]', sem_section.group(1)) if sem_section else []

    emb_section = re.search(r'## EMBED_LINKS\n((?:- .*\n?)*)', content)
    embed_links = re.findall(r'\[\[([^\]]+)\]\]', emb_section.group(1)) if emb_section else []

    anc_section = re.search(r'search_anchors:\n((?:\s+-\s.*\n?)*)', content)
    anchors = re.findall(r'-\s*([^\s#]+)', anc_section.group(1)) if anc_section else []

    return {'id': nid, 'impulse': imp, 'sem_links': sem_links,
            'embed_links': embed_links, 'anchors': anchors}


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
