#!/usr/bin/env python3
"""SPINE anchor validator — валидация search_anchors против канона.

Запуск:
  python tools/_check_anchors.py nodes/KEDR_001.md --dump anchors/anchor_dump.json
  python tools/_check_anchors.py nodes/KEDR_001.md --dump anchors/anchor_dump.json --quiet

Выход: 0 = PASS, 1 = WARN (новый якорь), 2 = FAIL (дубликат/формат).
"""

import json
import os
import re
import sys
from difflib import SequenceMatcher

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

FUZZY_THRESHOLD = 0.78
MAX_TOKENS = 5
MIN_TOKENS = 2
ANCHOR_PATTERN = re.compile(r'^[a-zа-яё0-9_]+$')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DUMP = os.environ.get(
    'SPINE_ANCHOR_DUMP',
    os.path.join(SCRIPT_DIR, '..', 'anchors', 'anchor_dump.json'),
)


def load_anchor_dump(path):
    if not os.path.exists(path):
        print(f"[WARN] anchor_dump.json not found: {path}")
        return set()
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    all_anchors = set()
    first_key = next(iter(data), "")
    is_new_format = not (first_key.startswith(("U", "APR", "PRE", "CROFT", "KEDR")))
    if is_new_format:
        for anchor in data.keys():
            a_clean = anchor.split('#')[0].strip()
            if a_clean:
                all_anchors.add(a_clean)
    else:
        for anchors in data.values():
            for a in anchors:
                a_clean = a.split('#')[0].strip()
                if a_clean:
                    all_anchors.add(a_clean)
    return all_anchors


def extract_anchors(node_path):
    if not os.path.exists(node_path):
        print(f"file not found: {node_path}")
        return []
    with open(node_path, 'r', encoding='utf-8') as f:
        content = f.read()

    parts = content.split('---', 2)
    if len(parts) < 3:
        print("YAML frontmatter not found")
        return []
    yaml_block = parts[1]

    anchors = []
    in_anchors = False
    for line in yaml_block.split('\n'):
        stripped = line.strip()
        if stripped.startswith('search_anchors:'):
            in_anchors = True
            continue
        if in_anchors:
            if stripped.startswith('- '):
                anchor = stripped.lstrip('- ').strip().split('#')[0].strip()
                if anchor:
                    anchors.append(anchor)
            elif stripped and not stripped.startswith('#'):
                break
    return anchors


def fuzzy_match(anchor, canonical_set, threshold=FUZZY_THRESHOLD):
    best_match = None
    best_score = 0.0
    anchor_lower = anchor.lower()
    for canonical in canonical_set:
        canon_lower = canonical.lower()
        if anchor_lower in canon_lower or canon_lower in anchor_lower:
            continue
        score = SequenceMatcher(None, anchor_lower, canon_lower).ratio()
        if score > best_score:
            best_score = score
            best_match = canonical
    if best_score >= threshold:
        return best_match, best_score
    return None, best_score


def check_format(anchor):
    errors = []
    if not ANCHOR_PATTERN.match(anchor):
        errors.append("format: use snake_case (a-z, a-ya, 0-9, _)")
    tokens = anchor.split('_')
    if len(tokens) > MAX_TOKENS:
        errors.append(f"tokens: {len(tokens)} > {MAX_TOKENS}")
    if len(tokens) < MIN_TOKENS:
        errors.append(f"tokens: {len(tokens)} < {MIN_TOKENS}")
    if anchor[0].isdigit():
        errors.append("starts with digit")
    return errors


def main():
    quiet = '--quiet' in sys.argv or '-q' in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith('-')]

    if len(args) < 1:
        print("usage: python _check_anchors.py <node_file> [--dump path] [--quiet]")
        sys.exit(0)

    node_path = args[0]
    dump_path = DEFAULT_DUMP
    if '--dump' in sys.argv:
        dump_idx = sys.argv.index('--dump')
        if dump_idx + 1 < len(sys.argv):
            dump_path = sys.argv[dump_idx + 1]

    node_name = os.path.basename(node_path)
    canonical = load_anchor_dump(dump_path)
    node_anchors = extract_anchors(node_path)

    if not node_anchors:
        print(f"FAIL {node_name} — anchors not found")
        sys.exit(2)

    format_errors = []
    duplicates = []
    new_anchors = []
    passed = []

    for anchor in node_anchors:
        anchor_clean = anchor.split('#')[0].strip()
        fmt_errs = check_format(anchor_clean)
        if fmt_errs:
            format_errors.append((anchor_clean, fmt_errs))
            continue
        if anchor_clean in canonical:
            passed.append(anchor_clean)
            continue
        best, score = fuzzy_match(anchor_clean, canonical)
        if best:
            duplicates.append((anchor_clean, best, round(score, 2)))
        else:
            new_anchors.append(anchor_clean)

    exit_code = 0
    issues = len(format_errors) + len(duplicates)

    if quiet:
        if issues > 0:
            print(f"FAIL {node_name}: {issues} issue(s)")
            for a, errs in format_errors:
                print(f"   FMT {a}: {errs[0]}")
            for a, best, sc in duplicates:
                print(f"   DUP {a} -> {best} ({sc})")
            exit_code = 2
        elif new_anchors:
            print(f"WARN {node_name}: {len(passed)} OK + {len(new_anchors)} new")
            exit_code = 1
        else:
            print(f"PASS {node_name}: {len(passed)} OK")
        sys.exit(exit_code)

    print(f"=== ANCHOR CHECK: {node_name} ===")
    print(f"node anchors: {len(node_anchors)} | canon: {len(canonical)}\n")
    if passed:
        print(f"OK ({len(passed)}):")
        for a in passed:
            print(f"   + {a}")
        print()
    if new_anchors:
        print(f"NEW ({len(new_anchors)}):")
        for a in new_anchors:
            print(f"   ? {a}")
        print("   -> verify: is there an existing anchor with the same meaning?\n")
        exit_code = 1
    if duplicates:
        print(f"DUPLICATES ({len(duplicates)}):")
        for a, best, sc in duplicates:
            print(f"   x '{a}' -> existing '{best}' ({sc})")
        print()
        exit_code = 2
    if format_errors:
        print(f"FORMAT ERRORS ({len(format_errors)}):")
        for a, errs in format_errors:
            for e in errs:
                print(f"   x '{a}' — {e}")
        print()
        exit_code = 2

    if exit_code == 0:
        print("ALL ANCHORS PASSED")
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
