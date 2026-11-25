#!/usr/bin/env python3
"""SPINE night daemon — nightly consolidation + self-audit (public/demo).

Two loops:
  «You»  — hot nodes by strategic_weight + answer to thoughts/inbox.md
  «Me»   — self-audit: broken YAML, empty SOURCE_BASE, isolated nodes,
            missing anchors, anchor synonyms

Usage:
  python tools/night_daemon.py --folder nodes
  python tools/night_daemon.py --folder nodes --todo-file TODO.md
"""

import argparse
import os
import re
from collections import defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
DEFAULT_NODES = os.path.join(ROOT, 'nodes')
DEFAULT_THOUGHTS = os.path.join(ROOT, 'thoughts')
INBOX = os.path.join(DEFAULT_THOUGHTS, 'inbox.md')


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

    data = {
        'id': os.path.basename(path).replace('.md', ''),
        'impulse': '',
        'weight': 0.0,
        'sem_links': [],
        'anchors': [],
        'source_base': '',
        'yaml_ok': content.startswith('---') and '---' in content[3:],
    }

    m = re.search(r'^id:\s*(\S+)', content, re.MULTILINE)
    if m:
        data['id'] = m.group(1)

    imp = extract_section(content, '# IMPULSE')
    if not imp:
        m = re.search(r'impulse:\s*[|>]\n((?:  .*\n?)*)', content)
        imp = m.group(1).strip() if m else ''
    else:
        imp = re.sub(r'^impulse:\s*[|>]\s*', '', imp).strip()
    data['impulse'] = imp

    m = re.search(r'strategic_weight:\s*([\d.]+)', content)
    if m:
        try:
            data['weight'] = float(m.group(1))
        except ValueError:
            pass

    m = re.search(r'semantic_links:\n((?:\s+-\s.*\n?)*)', content)
    if m:
        data['sem_links'] = re.findall(r'\[\[([^\]]+)\]\]', m.group(1))

    m = re.search(r'search_anchors:\n((?:\s+-\s.*\n?)*)', content)
    if m:
        data['anchors'] = re.findall(r'-\s*([^\s#]+)', m.group(1))

    data['source_base'] = extract_section(content, '# SOURCE_BASE')
    return data


def load_all(folders):
    nodes = {}
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for fn in sorted(os.listdir(folder)):
            if not fn.endswith('.md'):
                continue
            data = read_node(os.path.join(folder, fn))
            nodes[data['id']] = data
    return nodes


def audit(nodes):
    metrics = {
        'total': len(nodes),
        'yaml_broken': [],
        'source_empty': [],
        'isolated': [],
        'no_anchors': [],
    }
    roots = defaultdict(list)
    for nid, nd in nodes.items():
        if not nd['yaml_ok']:
            metrics['yaml_broken'].append(nid)
        if not nd['source_base']:
            metrics['source_empty'].append(nid)
        if not nd['sem_links']:
            metrics['isolated'].append(nid)
        if len(nd['anchors']) < 3:
            metrics['no_anchors'].append(nid)
        for a in nd['anchors']:
            roots[a.split('_')[0]].append(a)
    metrics['anchor_synonyms'] = {r: sorted(set(al))
                                  for r, al in roots.items() if len(set(al)) > 1}
    return metrics


def read_inbox():
    if not os.path.exists(INBOX):
        return ''
    with open(INBOX, 'r', encoding='utf-8') as f:
        return f.read().strip()


def answer_question(question, nodes):
    anchor_index = defaultdict(list)
    for nid, nd in nodes.items():
        for a in nd['anchors']:
            anchor_index[a].append(nid)
    tokens = re.findall(r'[a-zа-яё0-9_]+', question.lower())
    matched = set()
    for a in anchor_index:
        for t in tokens:
            if t and (t in a or a in t):
                matched.add(a)
    hit_ids = set()
    for a in matched:
        hit_ids.update(anchor_index[a])
    return sorted(hit_ids)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--folder', action='append', default=None,
                   help='folder with nodes (repeatable)')
    p.add_argument('--thoughts-dir', default=DEFAULT_THOUGHTS)
    p.add_argument('--todo-file', default=None,
                   help='optional file with open tasks (for the "You" loop)')
    p.add_argument('--top', type=int, default=5)
    args = p.parse_args()

    folders = args.folder or [DEFAULT_NODES]
    nodes = load_all(folders)
    ranked = sorted(nodes.values(),
                    key=lambda n: (n['weight'], len(n['sem_links'])),
                    reverse=True)
    met = audit(nodes)
    question = read_inbox()

    todo = []
    if args.todo_file and os.path.exists(args.todo_file):
        with open(args.todo_file, 'r', encoding='utf-8') as f:
            todo = [l.strip().lstrip('- ').strip()
                    for l in f if l.strip().startswith('-')]

    date = datetime.now().strftime('%Y-%m-%d')
    os.makedirs(args.thoughts_dir, exist_ok=True)
    out_path = os.path.join(args.thoughts_dir, date + '.md')

    lines = ['# Ночная консолидация — %s' % date, '']
    lines.append('## 🎯 Тебе')
    lines.append('')
    if todo:
        lines.append('### Чем заняться')
        for t in todo:
            lines.append('- %s' % t)
        lines.append('')
    lines.append('### На что обратить внимание')
    for nd in ranked[:args.top]:
        imp = nd['impulse'].replace('\n', ' ')[:100] or '—'
        lines.append('- **%s** (w=%.2f): %s' % (nd['id'], nd['weight'], imp))
    lines.append('')

    if question:
        hits = answer_question(question, nodes)
        lines.append('### Ответ на вопрос')
        lines.append('> %s' % question)
        if hits:
            for nid in hits[:5]:
                nd = nodes[nid]
                imp = nd['impulse'].replace('\n', ' ')[:100] or '—'
                lines.append('- **%s**: %s' % (nid, imp))
        else:
            lines.append('- по якорям точных попаданий нет')
        lines.append('')

    lines.append('## 🔧 Мне (self-audit)')
    lines.append('')
    lines.append('Нод: %d' % met['total'])
    lines.append('- битых YAML: %d' % len(met['yaml_broken']))
    lines.append('- пустых SOURCE_BASE: %d' % len(met['source_empty']))
    lines.append('- изолированных: %d' % len(met['isolated']))
    lines.append('- без якорей (<3): %d' % len(met['no_anchors']))
    lines.append('- групп синонимов: %d' % len(met['anchor_synonyms']))
    lines.append('')
    recs = []
    if met['yaml_broken']:
        recs.append('починить YAML у %d нод' % len(met['yaml_broken']))
    if met['source_empty']:
        recs.append('мигрировать SOURCE_BASE у %d нод' % len(met['source_empty']))
    if met['isolated']:
        recs.append('прогнать _crosslink для %d изолированных' % len(met['isolated']))
    if met['no_anchors']:
        recs.append('дописать якоря %d нодам' % len(met['no_anchors']))
    if met['anchor_synonyms']:
        recs.append('слить %d групп синонимов в канон' % len(met['anchor_synonyms']))
    lines.append('### Рекомендации')
    lines.extend('- %s' % r for r in recs) if recs else lines.append('- граф здоров')

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    print('nodes: %d | yaml_broken: %d | source_empty: %d | isolated: %d' % (
        met['total'], len(met['yaml_broken']), len(met['source_empty']),
        len(met['isolated'])))
    print('briefing: ' + out_path)


if __name__ == '__main__':
    main()
