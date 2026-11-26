#!/usr/bin/env python3
"""SPINE node I/O — canonical read/write of SPINE nodes.

Single source of truth for parsing SPINE node files (Markdown + YAML
frontmatter). All tools (_build_index, _crosslink, _wander, mcp_server,
night_daemon, critic) should read nodes through this module so they see the
same structure. Zero external dependencies (stdlib only).

Contract
--------
- A node is: YAML frontmatter between the first ``---`` line and the next
  ``---`` line, followed by a Markdown body.
- Frontmatter lists may be block style (``- item``) or inline (``[a, b]``).
- In the body, ``# SOURCE_BASE`` is the LAST H1 section. It swallows
  everything after it up to (but excluding) any ``## `` H2 metadata sections
  (``## SEMANTIC_LINKS`` / ``## EMBED_LINKS``) or the final closing ``---``.
  This protects raw logs containing ``#`` or ``---`` from being truncated.
"""

import os
import re

# The first ``---`` opens the frontmatter; the closing one must be a ``---``
# on its own line. Everything after it is the body.
_LIST_ITEM_RE = re.compile(r'^\s*-\s+(.*)$')


def split_frontmatter(content):
    """Return (frontmatter_text, body) or (None, content) if malformed.

    frontmatter_text has no surrounding newlines; body keeps any blank lines
    that follow the closing ``---`` so the file can be reassembled exactly.
    """
    if not content.startswith('---'):
        return None, content
    lines = content.split('\n')
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            return '\n'.join(lines[1:i]), '\n'.join(lines[i + 1:])
    return None, content


def _unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


def _strip_comment(s):
    """Strip a trailing ``# comment`` (but keep ``#`` inside quotes)."""
    return s.split('#')[0].strip()


def parse_list(value):
    """Parse a list given as inline ``[a, b]`` or block ``- a\\n- b`` text."""
    if isinstance(value, list):
        return value
    if value is None:
        return []
    text = value.strip()
    if text.startswith('['):
        inner = text[1:-1]
        return [_unquote(x) for x in inner.split(',') if x.strip()]
    # block list (lines like "- item" with optional # comment)
    out = []
    for line in text.split('\n'):
        m = _LIST_ITEM_RE.match(line)
        if m:
            item = _strip_comment(m.group(1))
            item = _unquote(item)
            if item:
                out.append(item)
    return out


def parse_frontmatter(fm_text):
    """Parse the YAML subset used by SPINE into a dict.

    Handles: scalars, inline lists ``[a, b]``, block lists ``- item`` and
    simple nested maps (e.g. ``chronology:`` with ``roots:`` / ``after:``).
    """
    data = {}
    lines = fm_text.split('\n')
    i, n = 0, len(lines)

    def _indent(l):
        return len(l) - len(l.lstrip(' \t'))

    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            i += 1
            continue

        m = re.match(r'^([A-Za-z_][\w.-]*):\s*(.*)$', line)
        if not m:
            i += 1
            continue

        key = m.group(1)
        rest = m.group(2).strip()

        # Inline list.
        if rest.startswith('[') and rest.endswith(']'):
            data[key] = parse_list(rest)
            i += 1
            continue

        # Block value: collect following lines more indented than the key.
        if rest == '':
            base_indent = _indent(line)
            block = []
            j = i + 1
            while j < n:
                l2 = lines[j]
                if not l2.strip():
                    block.append(l2)
                    j += 1
                    continue
                if _indent(l2) > base_indent or l2.strip().startswith('#'):
                    block.append(l2)
                    j += 1
                    continue
                break
            block_text = '\n'.join(block)
            if any(_LIST_ITEM_RE.match(b) for b in block if b.strip()):
                data[key] = parse_list(block_text)
            else:
                data[key] = _parse_block_map(block_text)
            i = j
            continue

        # Scalar (strip trailing comment, but keep value before it).
        data[key] = _unquote(_strip_comment(rest))
        i += 1

    return data


def _parse_block_map(text):
    out = {}
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = re.match(r'^([A-Za-z_][\w.-]*):\s*(.*)$', line)
        if m:
            out[m.group(1)] = _unquote(_strip_comment(m.group(2)))
    return out


def extract_section(content, name):
    """Extract one H1 body section (e.g. ``# IMPULSE``).

    ``SOURCE_BASE`` is special: raw logs may contain ``#`` comment lines and
    ``---`` separators, so it only stops at a ``## `` H2 metadata section or
    the FINAL closing ``---`` (the last non-empty line of the file).
    """
    marker = '# ' + name
    lines = content.split('\n')
    start = None
    for idx, line in enumerate(lines):
        if line.strip() == marker:
            start = idx
            break
    if start is None:
        return ''

    is_source = (name == 'SOURCE_BASE')
    last_nonempty = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            last_nonempty = i
            break

    out = []
    for i, line in enumerate(lines[start + 1:], start=start + 1):
        s = line.strip()
        # H2 metadata boundary — always stops (EMBED_LINKS / SEMANTIC_LINKS).
        if s.startswith('## '):
            break
        if is_source:
            # SOURCE_BASE: do NOT stop on '# ' (raw logs may contain comments);
            # stop on '---' only if it is the final closing separator.
            if s == '---' and i == last_nonempty:
                break
        else:
            # Regular sections stop at the next H1 or any standalone '---'.
            if (s.startswith('# ') and s != marker) or s == '---':
                break
        out.append(line)
    return '\n'.join(out).strip()


def parse_body(body):
    """Return {section_name: text} for H1 sections plus H2 link sections."""
    sections = {}
    for name in ('IMPULSE', 'SUMMARY', 'CLEANED_DATA', 'IMPACT', 'SOURCE_BASE'):
        sections[name.lower()] = extract_section(body, name)

    for h2, key in (('## SEMANTIC_LINKS', 'semantic_links_body'),
                    ('## EMBED_LINKS', 'embed_links')):
        m = re.search(re.escape(h2) + r'\s*\n((?:- .*\n?)*)', body)
        if m:
            sections[key] = re.findall(r'\[\[([^\]]+)\]\]', m.group(1))
        else:
            sections[key] = []
    return sections


def read_node(path):
    """Read a node file into a canonical dict.

    Returns ``None`` if the file has no valid frontmatter.
    """
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    fm_text, body = split_frontmatter(content)
    if fm_text is None:
        return None

    fm = parse_frontmatter(fm_text)
    secs = parse_body(body)

    nid = fm.get('id') or os.path.basename(path).replace('.md', '')

    impulse = secs.get('impulse', '')
    if not impulse:
        # Legacy: some nodes stored the impulse in the YAML frontmatter.
        m = re.search(r'impulse:\s*[|>]\s*\n((?:  .*\n?)*)', fm_text)
        if m:
            impulse = m.group(1).strip()

    sem = []
    # semantic_links in YAML are full "[[TARGET]]::reason" strings; tools
    # traverse by target id, so extract the inner [[...]] part.
    for link in (fm.get('semantic_links') or []):
        m = re.search(r'\[\[([^\]]+)\]\]', link)
        if m:
            sem.append(m.group(1))
    # Merge body ## SEMANTIC_LINKS for backward compatibility.
    for l in secs.get('semantic_links_body', []):
        if l not in sem:
            sem.append(l)

    return {
        'id': nid,
        'path': path,
        'frontmatter': fm,
        'tags': fm.get('tags') or [],
        'domain': fm.get('domain'),
        'hub': fm.get('hub'),
        'constellation': fm.get('constellation'),
        'vectors': fm.get('vectors') or [],
        'search_anchors': fm.get('search_anchors') or [],
        'chronology': fm.get('chronology') or {},
        'semantic_links': sem,
        'embed_links': secs.get('embed_links', []),
        'impulse': impulse,
        'summary': secs.get('summary', ''),
        'cleaned_data': secs.get('cleaned_data', ''),
        'impact': secs.get('impact', ''),
        'source_base': secs.get('source_base', ''),
        # dev-overlay fields (CODE_MEMORY preset) — generic frontmatter pass-through
        'kind': fm.get('kind'),
        'status': fm.get('status'),
        'code_refs': fm.get('code_refs') or [],
        'repo_ref': fm.get('repo_ref') or {},
    }


def add_semantic_link(path, target, reason):
    """Safely append ``[[target]]::reason`` to the frontmatter semantic_links.

    Handles a missing field and an empty ``semantic_links: []`` without
    corrupting the YAML. Returns True if the file was changed.
    """
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    fm_text, body = split_frontmatter(content)
    if fm_text is None:
        return False

    fm = parse_frontmatter(fm_text)
    links = list(fm.get('semantic_links') or [])
    target_mark = '[[%s]]' % target
    if any(target_mark in l for l in links):
        return False

    new_link = '[[%s]]::%s' % (target, reason)
    fm_text = fm_text.rstrip('\n')

    if 'semantic_links:' in fm_text:
        # Clear an empty inline list before inserting, then append.
        fm_new = re.sub(r'semantic_links:\s*\[\]', 'semantic_links:', fm_text, count=1)
        fm_new = fm_new.replace(
            'semantic_links:', 'semantic_links:\n  - "%s"' % new_link, 1)
    else:
        fm_new = fm_text.rstrip() + '\nsemantic_links:\n  - "%s"' % new_link

    # Reassemble with explicit newlines around both '---' delimiters so they
    # never glue to the first YAML key or to the body heading.
    new_content = '---\n' + fm_new + '\n---\n' + body
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_content)
    return True


if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        d = read_node(p)
        if d is None:
            print('MALFORMED: %s' % p)
            continue
        print('%s | domain=%s | anchors=%d | sem=%d | embed=%d | src=%dB' % (
            d['id'], d['domain'], len(d['search_anchors']),
            len(d['semantic_links']), len(d['embed_links']),
            len(d['source_base'])))
