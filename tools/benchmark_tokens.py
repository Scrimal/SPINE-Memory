#!/usr/bin/env python3
"""SPINE token benchmark — measure token savings of progressive disclosure.

Compares two retrieval strategies for each raw chunk:
  1. raw     — load the full raw chunk (naive RAG).
  2. layered — load impulse + summary + cleaned_data only (no source_base).

Token counting is local and free (0 cost): tiktoken if available, otherwise a
conservative chars/4 heuristic. The layered strategy never touches source_base,
which is reserved for deep drill-down and fine-tuning.

Usage:
  python tools/benchmark_tokens.py
"""

import os
import re

try:
    from spine_memory._node_io import read_node, find_spine_root
except ImportError:
    from _node_io import read_node, find_spine_root

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = find_spine_root()
RAW_DIR = os.path.join(ROOT, 'raw')
NODES_DIR = os.path.join(ROOT, 'nodes')

try:
    import tiktoken
    _enc = tiktoken.get_encoding('o200k_base')
    TOKENIZER = 'tiktoken/o200k_base'
    def count_tokens(text):
        return len(_enc.encode(text))
except ImportError:
    TOKENIZER = 'chars/4 (approximate)'
    def count_tokens(text):
        return max(1, len(text) // 4)


def main():
    if not os.path.isdir(RAW_DIR):
        print('raw dir not found:', RAW_DIR)
        return

    print('SPINE TOKEN BENCHMARK')
    print('tokenizer: %s\n' % TOKENIZER)

    rows = []
    for fn in sorted(os.listdir(RAW_DIR)):
        if not fn.endswith('.md'):
            continue
        num = re.search(r'(\d+)$', fn.replace('.md', ''))
        if not num:
            continue
        num = num.group(1)
        node_path = None
        if os.path.isdir(NODES_DIR):
            for cand in sorted(os.listdir(NODES_DIR)):
                if cand.endswith('_%s.md' % num):
                    node_path = os.path.join(NODES_DIR, cand)
                    break
        if not node_path:
            continue

        with open(os.path.join(RAW_DIR, fn), 'r', encoding='utf-8') as f:
            raw_text = f.read()

        d = read_node(node_path) or {}
        layered_text = '\n\n'.join([
            d.get('impulse', ''),
            d.get('summary', ''),
            d.get('cleaned_data', ''),
        ])

        raw_tokens = count_tokens(raw_text)
        layered_tokens = count_tokens(layered_text)
        economy = (1 - layered_tokens / raw_tokens) * 100 if raw_tokens else 0.0

        rows.append((num, raw_tokens, layered_tokens, economy))
        print('KEDR_%s: raw %d tok | layered %d tok | saving %.0f%%' % (
            num, raw_tokens, layered_tokens, economy))

    if not rows:
        print('no matching raw/node pairs found')
        return

    avg = sum(r[3] for r in rows) / len(rows)
    total_raw = sum(r[1] for r in rows)
    total_layered = sum(r[2] for r in rows)
    print('\nTOTAL: raw %d tok -> layered %d tok' % (total_raw, total_layered))
    print('AVERAGE SAVING: %.0f%%' % avg)
    print('(source_base is never loaded during routing/synthesis; it is the '
          'lossless basement for deep drill-down and fine-tuning)')


if __name__ == '__main__':
    main()
