#!/usr/bin/env python3
"""SPINE quality audit — глобальный аудит узлов, якорей и метрик.

Проверяет: наличие обязательных полей, лимиты секций, ratio SOURCE/RAW,
повторное использование якорей, возможные синонимы (общий корень).

Запуск:
  python tools/_quality_audit.py --nodes nodes --raw raw
  Результат: audit_report.txt
"""

import argparse
import os
import re
import sys
from collections import Counter, defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def extract_section(content, name):
    """Извлекает тело секции '# name' до следующего заголовка '# ' или '---'."""
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


def count_lines(text):
    if not text:
        return 0
    return len([l for l in text.split('\n') if l.strip()])


def read_node(path, raw_folder):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    fm = {}
    fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('#') and not line.startswith('-'):
                k, v = line.split(':', 1)
                fm[k.strip()] = v.strip().strip('"')

    nid = fm.get('id', os.path.basename(path).replace('.md', ''))
    num_id = re.search(r'(\d+)$', nid)
    num_id = num_id.group(1) if num_id else ''

    result = {
        'id': nid,
        'num_id': num_id,
        'domain': fm.get('domain', ''),
        'hub': fm.get('hub', ''),
        'content': content,
        'issues': [],
    }

    if not result['domain']:
        result['issues'].append('[NO_DOMAIN]')
    if not result['hub']:
        result['issues'].append('[NO_HUB]')

    anc = re.findall(r'search_anchors:\n((?:\s+-\s.*\n?)*)', content)
    anchors = re.findall(r'-\s*([^\s#]+)', anc[0]) if anc else []
    result['anchors'] = anchors

    vec = re.findall(r'vectors:\n((?:\s+-\s.*\n?)*)', content)
    vectors = re.findall(r'-\s*(.+)', vec[0]) if vec else []
    result['vectors'] = len(vectors)
    if result['vectors'] < 1:
        result['issues'].append('[NO_VEC]')

    sem = re.findall(r'semantic_links:\n((?:\s+-\s.*\n?)*)', content)
    sem_links = re.findall(r'\[\[(.+?)\]\]', sem[0]) if sem else []
    result['sem_links'] = len(sem_links)
    if result['sem_links'] < 1:
        result['issues'].append('[NO_SEM]')

    if 'roots:' not in content and 'after:' not in content:
        result['issues'].append('[NO_CHRONO]')

    if not content.strip().endswith('---'):
        result['issues'].append('[NO_CLOSE]')

    # Секции нового формата
    imp = extract_section(content, '# IMPULSE')
    imp_lines = count_lines(imp)
    result['impulse'] = imp_lines
    if imp_lines > 2:
        result['issues'].append('IMPULSE:%d' % imp_lines)

    summ = extract_section(content, '# SUMMARY')
    sum_lines = count_lines(summ)
    result['summary'] = sum_lines
    if sum_lines > 5:
        result['issues'].append('SUMMARY:%d' % sum_lines)

    cln = extract_section(content, '# CLEANED_DATA')
    cln_lines = count_lines(cln)
    result['cleaned'] = cln_lines
    if cln_lines < 10:
        result['issues'].append('CLEANED:%d' % cln_lines)

    src = extract_section(content, '# SOURCE_BASE')
    src_lines = count_lines(src)
    result['source'] = src_lines

    if sum_lines > 0 and cln_lines > 0 and sum_lines > cln_lines / 2:
        result['issues'].append('S>C_RATIO:%.1f' % (sum_lines / max(cln_lines, 1)))

    if imp_lines > 0 and sum_lines > 0 and imp_lines > sum_lines:
        result['issues'].append('IMP>SUM')

    if '# IMPACT' not in content:
        result['issues'].append('[NO_IMPACT]')

    chrono_text = ''
    cm = re.search(r'chronology:\n((?:  .*\n?)*)', content)
    if cm:
        chrono_text = cm.group(1)
    after_match = re.search(r'after:(.*)', chrono_text)
    has_typed_after = after_match and (':' in after_match.group(1))
    if 'after:' in chrono_text and not has_typed_after:
        result['issues'].append('[CHRONO_NOTYPED]')

    if len(anchors) < 3:
        result['issues'].append('ANCHORS:%d' % len(anchors))
    if len(anchors) > 5:
        result['issues'].append('ANCHORS:%d' % len(anchors))

    # SOURCE_BASE / raw ratio
    if num_id and raw_folder:
        raw_path = os.path.join(raw_folder, 'U' + num_id + '.md')
        if os.path.exists(raw_path):
            raw_size = os.path.getsize(raw_path)
            src_chars = len(src.encode('utf-8'))
            src_pct = src_chars * 100 / max(raw_size, 1)
            result['src_pct'] = int(src_pct)
            if src_pct < 40:
                result['issues'].append('SRC_RAW:%d%%' % int(src_pct))
        else:
            result['src_pct'] = 0
    else:
        result['src_pct'] = 0

    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--nodes', default='nodes')
    p.add_argument('--raw', default='raw')
    p.add_argument('--report', default='audit_report.txt')
    args = p.parse_args()

    if not os.path.exists(args.nodes):
        print('NOT FOUND:', args.nodes)
        return

    nodes = []
    all_anchors = defaultdict(list)
    for f in sorted(os.listdir(args.nodes)):
        if not f.endswith('.md'):
            continue
        data = read_node(os.path.join(args.nodes, f), args.raw)
        nodes.append(data)
        for a in data.get('anchors', []):
            all_anchors[a].append(data['id'])

    total = len(nodes)
    clean = sum(1 for d in nodes if not d['issues'])

    for d in nodes:
        shared = 0
        for a in d.get('anchors', []):
            if len(all_anchors.get(a, [])) > 1:
                shared += 1
        d['shared_anchors'] = shared

    singletons = sum(1 for a, n in all_anchors.items() if len(n) == 1)
    shared_anchors = sum(1 for a, n in all_anchors.items() if len(n) > 1)
    total_anchors = len(all_anchors)

    roots = defaultdict(list)
    for a in all_anchors:
        roots[a.split('_')[0]].append(a)
    synonyms = {r: al for r, al in roots.items() if len(al) > 1}

    issue_counts = Counter()
    for d in nodes:
        for i in d['issues']:
            base = re.sub(r':\d+\.?\d*', '', i)
            issue_counts[base] += 1

    lines = []
    lines.append('=' * 60)
    lines.append('QUALITY AUDIT')
    lines.append('Nodes folder: ' + args.nodes)
    lines.append('Nodes: %d | Clean: %d | With issues: %d' % (total, clean, total - clean))
    lines.append('=' * 60)

    for d in nodes:
        tag = 'OK' if not d['issues'] else 'ISS'
        extra = ' i:%d s:%d c:%d src:%d s%%:%d a:%d' % (
            d.get('impulse', 0), d.get('summary', 0), d.get('cleaned', 0),
            d.get('source', 0), d.get('src_pct', 0), d.get('shared_anchors', 0))
        flags = ', '.join(d['issues'][:5]) if d['issues'] else '-'
        lines.append('%-4s | %-14s | %-6s | %s%s' % (
            d['id'], d['domain'], tag, flags[:60], extra))

    lines.append('')
    lines.append('=' * 60)
    lines.append('ANCHOR STATS')
    lines.append('=' * 60)
    lines.append('Total anchors:  %d' % total_anchors)
    lines.append('Shared:         %d (%d%%)' % (shared_anchors, shared_anchors * 100 // max(total_anchors, 1)))
    lines.append('Singletons:     %d (%d%%)' % (singletons, singletons * 100 // max(total_anchors, 1)))
    if synonyms:
        lines.append('')
        lines.append('POSSIBLE SYNONYMS (same root):')
        for root, al in sorted(synonyms.items())[:15]:
            lines.append('  %s: %s' % (root, ', '.join(al[:4])))

    lines.append('')
    lines.append('=' * 60)
    lines.append('ISSUE STATS')
    lines.append('=' * 60)
    for issue, count in issue_counts.most_common():
        pct = count * 100 // total
        bar = '*' * min(count // 2, 40)
        lines.append('%-20s %3d (%2d%%) %s' % (issue[:20], count, pct, bar))

    if nodes:
        avg_imp = sum(d['impulse'] for d in nodes) / len(nodes)
        avg_sum = sum(d['summary'] for d in nodes) / len(nodes)
        avg_cln = sum(d['cleaned'] for d in nodes) / len(nodes)
        avg_src = sum(d['source'] for d in nodes) / len(nodes)
        avg_srcpct = sum(d['src_pct'] for d in nodes) / len(nodes)
        lines.append('')
        lines.append('AVERAGES (%d nodes)' % len(nodes))
        lines.append('IMPULSE: %.1f (lim 2) | SUMMARY: %.1f (lim 5) | CLEANED: %.1f' % (avg_imp, avg_sum, avg_cln))
        lines.append('SOURCE: %.1f lines (lim 15) | SRC/RAW: %.0f%%' % (avg_src, avg_srcpct))

    report = '\n'.join(lines)
    with open(args.report, 'w', encoding='utf-8') as f:
        f.write(report)
    print(report[:3500])
    print('\nFull report: ' + args.report)


if __name__ == '__main__':
    main()
