#!/usr/bin/env python3
"""SPINE night daemon — nightly consolidation + self-audit (public/demo).

Two loops:
  «You» — hot nodes (strategic_weight with temporal decay) + answer to
          thoughts/inbox.md (anchor match with stopwords).
  «Me»  — self-audit: broken YAML, empty SOURCE_BASE, isolated nodes,
          dead links, missing inlinks, missing anchors, anchor synonyms.
  Optional --autoheal: rebuild reverse_index.json + anchor canon after audit.

Usage:
  python tools/night_daemon.py --folder nodes
  python tools/night_daemon.py --folder nodes --autoheal
"""

import argparse
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)

try:
    from spine_memory import _node_io
except ImportError:
    import _node_io
DEFAULT_NODES = os.path.join(ROOT, 'nodes')
DEFAULT_THOUGHTS = os.path.join(ROOT, 'thoughts')
INBOX = os.path.join(DEFAULT_THOUGHTS, 'inbox.md')

STOPWORDS = set(
    'в на как что и для с по от из о при до не но а у за к или это он она они '
    'мы вы ты мне нас тебе чем кто чего где когда почему зачем какой какая '
    'какие сегодня завтра про без под над об'.split()
)
ID_RE = re.compile(r'^[A-Za-z]+[_-]?\d+')


def decay_factor(days):
    if days < 14:
        return 1.0
    if days < 30:
        return 0.9
    if days < 90:
        return 0.7
    return 0.5


def _node_stamp(content, path):
    for key in ('last_accessed', 'updated', 'created'):
        m = re.search(r'^%s:\s*(\d{4}-\d{2}-\d{2})' % key, content, re.MULTILINE)
        if m:
            try:
                return datetime.strptime(m.group(1), '%Y-%m-%d').timestamp()
            except ValueError:
                pass
    return os.path.getmtime(path)


def read_node(path):
    d = _node_io.read_node(path)
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    data = {
        'id': d['id'] if d else os.path.basename(path).replace('.md', ''),
        'impulse': d['impulse'] if d else '',
        'weight': 0.0,
        'sem_links': d['semantic_links'] if d else [],
        'anchors': d['search_anchors'] if d else [],
        'code_refs': d['code_refs'] if d else [],
        'repo_ref': d['repo_ref'] if d else {},
        'source_base': d['source_base'] if d else '',
        'yaml_ok': d is not None,
        'mtime': _node_stamp(content, path),
    }
    m = re.search(r'strategic_weight:\s*([\d.]+)', content)
    if m:
        try:
            data['weight'] = float(m.group(1))
        except ValueError:
            pass
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


def audit(nodes, repo=None):
    metrics = {
        'total': len(nodes),
        'yaml_broken': [],
        'source_empty': [],
        'isolated': [],
        'no_anchors': [],
        'dead_links': [],
        'stale_code_refs': [],
    }
    roots = defaultdict(list)
    incoming = set()
    all_ids = set(nodes.keys())

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
        for t in nd['sem_links']:
            incoming.add(t)
            if ID_RE.match(t) and t not in all_ids:
                metrics['dead_links'].append('%s -> %s' % (nid, t))
        if repo:
            for ref in nd['code_refs']:
                p = ref.split('::')[0].split('@')[0].strip()
                if p and not os.path.exists(os.path.join(repo, p)):
                    metrics['stale_code_refs'].append('%s -> %s' % (nid, p))

    metrics['no_incoming'] = sorted(
        nid for nid in all_ids if nid not in incoming and ID_RE.match(nid)
    )
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
    tokens = [t for t in re.findall(r'[a-zа-яё0-9_]+', question.lower())
              if len(t) > 2 and t not in STOPWORDS]
    matched = set()
    for a in anchor_index:
        for t in tokens:
            if t in a or a in t:
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
    p.add_argument('--autoheal', action='store_true',
                   help='rebuild reverse_index + anchor canon after audit')
    p.add_argument('--repo', default=None,
                   help='git repo root to resolve code_refs against')
    args = p.parse_args()

    now = time.time()
    folders = args.folder or [DEFAULT_NODES]
    nodes = load_all(folders)
    met = audit(nodes, args.repo)
    question = read_inbox()

    todo = []
    if args.todo_file and os.path.exists(args.todo_file):
        with open(args.todo_file, 'r', encoding='utf-8') as f:
            todo = [l.strip().lstrip('- ').strip()
                    for l in f if l.strip().startswith('-')]

    def eff_weight(nd):
        days = (now - nd['mtime']) / 86400.0
        return nd['weight'] * decay_factor(days)

    ranked = sorted(nodes.values(),
                    key=lambda n: (eff_weight(n), len(n['sem_links'])),
                    reverse=True)

    if args.autoheal:
        subprocess.run([sys.executable, os.path.join(BASE, '_build_index.py')],
                       check=False)

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
        lines.append('- **%s** (w=%.2f): %s' % (nd['id'], eff_weight(nd), imp))
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
        if os.path.exists(INBOX):
            os.remove(INBOX)

    lines.append('## 🔧 Мне (self-audit)')
    lines.append('')
    lines.append('Нод: %d' % met['total'])
    lines.append('- битых YAML: %d' % len(met['yaml_broken']))
    lines.append('- пустых SOURCE_BASE: %d' % len(met['source_empty']))
    lines.append('- изолированных: %d' % len(met['isolated']))
    lines.append('- битых ссылок: %d' % len(met['dead_links']))
    lines.append('- без входящих: %d' % len(met['no_incoming']))
    lines.append('- без якорей (<3): %d' % len(met['no_anchors']))
    lines.append('- групп синонимов: %d' % len(met['anchor_synonyms']))
    lines.append('- протухших code_refs: %d' % len(met['stale_code_refs']))
    lines.append('')
    recs = []
    if met['yaml_broken']:
        recs.append('починить YAML у %d нод' % len(met['yaml_broken']))
    if met['source_empty']:
        recs.append('мигрировать SOURCE_BASE у %d нод' % len(met['source_empty']))
    if met['isolated']:
        recs.append('прогнать _crosslink для %d изолированных' % len(met['isolated']))
    if met['dead_links']:
        recs.append('починить %d битых ссылок' % len(met['dead_links']))
    if met['no_incoming']:
        recs.append('дать входящие связи %d узлам' % len(met['no_incoming']))
    if met['no_anchors']:
        recs.append('дописать якоря %d нодам' % len(met['no_anchors']))
    if met['anchor_synonyms']:
        recs.append('слить %d групп синонимов в канон' % len(met['anchor_synonyms']))
    if met['stale_code_refs']:
        recs.append('обновить %d протухших ссылок на код' % len(met['stale_code_refs']))
    lines.append('### Рекомендации')
    lines.extend('- %s' % r for r in recs) if recs else lines.append('- граф здоров')

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    print('nodes: %d | yaml_broken: %d | source_empty: %d | isolated: %d' % (
        met['total'], len(met['yaml_broken']), len(met['source_empty']),
        len(met['isolated'])))
    print('dead_links: %d | no_incoming: %d | synonyms: %d | inbox: %s' % (
        len(met['dead_links']), len(met['no_incoming']),
        len(met['anchor_synonyms']), 'yes' if question else 'no'))
    print('briefing: ' + out_path)


if __name__ == '__main__':
    main()
