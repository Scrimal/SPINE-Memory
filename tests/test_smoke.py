#!/usr/bin/env python3
"""Smoke tests for SPINE-Memory core (stdlib unittest, no pytest).

Run:
  python -m unittest discover -s tests
"""

import os
import sys
import tempfile
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'tools'))

try:
    from spine_memory import _node_io
except ImportError:
    import _node_io

NODES = os.path.join(BASE, 'nodes')


class TestReadNode(unittest.TestCase):
    def test_read_kedr_001(self):
        d = _node_io.read_node(os.path.join(NODES, 'KEDR_001.md'))
        self.assertIsNotNone(d)
        self.assertEqual(d['id'], 'KEDR_001')
        self.assertEqual(d['domain'], 'Связь')
        self.assertGreaterEqual(len(d['search_anchors']), 3)
        self.assertIn('KEDR_002', d['semantic_links'])
        self.assertTrue(d['source_base'])

    def test_parse_inline_and_block_lists(self):
        self.assertEqual(_node_io.parse_list('[a, b, c]'), ['a', 'b', 'c'])
        self.assertEqual(_node_io.parse_list('- a\n- b\n'), ['a', 'b'])


class TestAddSemanticLink(unittest.TestCase):
    def _write(self, content):
        p = tempfile.mktemp(suffix='.md')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(content)
        return p

    def test_add_to_node_without_field(self):
        # Regression: a node with NO semantic_links must not get a
        # leading-space ' semantic_links:' (it would become nested YAML and
        # unreadable by the top-level key parser).
        content = ('---\nid: T1\ndomain: X\nsearch_anchors:\n'
                   '  - aaa\n  - bbb\n  - ccc\n---\n\n'
                   '# IMPULSE\nimp\n\n# SOURCE_BASE\nraw\n')
        p = self._write(content)
        try:
            self.assertTrue(_node_io.add_semantic_link(p, 'T2', 'reason'))
            with open(p, 'r', encoding='utf-8') as f:
                out = f.read()
            self.assertNotIn('\n semantic_links:', out)
            self.assertIn('\nsemantic_links:\n', out)
            d = _node_io.read_node(p)
            self.assertIn('T2', d['semantic_links'])
        finally:
            os.remove(p)

    def test_add_existing_link_is_noop(self):
        content = ('---\nid: T1\ndomain: X\nsemantic_links:\n'
                   '  - "[[T2]]::x"\nsearch_anchors:\n'
                   '  - aaa\n  - bbb\n  - ccc\n---\n\n# IMPULSE\nimp\n')
        p = self._write(content)
        try:
            self.assertFalse(_node_io.add_semantic_link(p, 'T2', 'x'))
        finally:
            os.remove(p)


class TestSourceBaseProtection(unittest.TestCase):
    def test_source_base_not_truncated(self):
        # SOURCE_BASE must swallow '#' comment lines and mid-file '---'.
        content = ('---\nid: T1\ndomain: X\nsearch_anchors:\n'
                   '  - aaa\n  - bbb\n  - ccc\n---\n\n'
                   '# IMPULSE\nimp\n\n# SOURCE_BASE\n'
                   'line1\n# comment inside\n---\nline after\nlast\n')
        p = tempfile.mktemp(suffix='.md')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(content)
        try:
            d = _node_io.read_node(p)
            self.assertIn('# comment inside', d['source_base'])
            self.assertIn('line after', d['source_base'])
            self.assertIn('last', d['source_base'])
        finally:
            os.remove(p)


if __name__ == '__main__':
    unittest.main()
