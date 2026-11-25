#!/usr/bin/env python3
"""SPINE embed links importer — inject precomputed embedding links.

The agent never computes vectors; an external GPU worker does. This tool only
stores the result into the `## EMBED_LINKS` body section of nodes.

Input JSON format:
  {"NODE_ID": [["TARGET_ID", score], ...], ...}

Usage:
  python tools/_embed_links.py --input embed_links.json --folder nodes
"""

import argparse
import json
import os


def inject_embed_links(content, links):
    lines = content.split('\n')
    # drop any existing EMBED_LINKS section
    out = []
    skip = False
    for line in lines:
        s = line.strip()
        if s.startswith('## EMBED_LINKS'):
            skip = True
            continue
        if skip and s.startswith('## ') and s != '## EMBED_LINKS':
            skip = False
        if not skip:
            out.append(line)

    text = '\n'.join(out).rstrip()
    section = '## EMBED_LINKS\n' + '\n'.join(
        '- [[%s]] (%.3f)' % (t, float(sc)) for t, sc in links
    )
    if text.endswith('---'):
        text = text[:-3].rstrip() + '\n\n' + section + '\n---\n'
    else:
        text = text + '\n\n' + section + '\n'
    return text


def main():
    p = argparse.ArgumentParser(
        description='Inject precomputed embedding links into SPINE nodes.'
    )
    p.add_argument('--input', required=True, help='path to embed links JSON')
    p.add_argument('--folder', default='nodes', help='folder with nodes')
    args = p.parse_args()

    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    applied = 0
    for nid, links in data.items():
        path = os.path.join(args.folder, nid + '.md')
        if not os.path.exists(path):
            print('skip (not found): %s' % nid)
            continue
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        new = inject_embed_links(content, links)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new)
        applied += 1
        print('embed links: %s <- %d links' % (nid, len(links)))

    print('applied: %d nodes' % applied)


if __name__ == '__main__':
    main()
