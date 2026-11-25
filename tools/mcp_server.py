#!/usr/bin/env python3
"""SPINE MCP server — expose the SPINE-Memory graph to MCP clients.

Thin wrapper over the SPINE node format: any MCP client (Claude Desktop,
Cursor, Windsurf, ...) can call graph tools directly.

Install:
  pip install -r requirements.txt

Run (stdio transport, as required by MCP clients):
  python tools/mcp_server.py

Tools:
  spine_list_nodes()              -> node ids
  spine_wander(start, hops)       -> impulse chain through the graph
  spine_read_node(id, layer)      -> one layer of a node
  spine_search_anchors(anchor)    -> nodes matching an anchor

Resources:
  spine://nodes/{node_id}         -> full node markdown
  spine://methodology             -> methodology spec (EN)
"""

import json
import os
import re
import sys

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - fallback to the standalone package
    from fastmcp import FastMCP

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import _node_io
NODES_DIR = os.path.join(BASE, '..', 'nodes')
METHODOLOGY_EN = os.path.join(BASE, '..', 'methodology', 'SPINE_METHODOLOGY_EN.md')

LAYERS = ('impulse', 'summary', 'cleaned', 'impact', 'source_base')


def read_node(path):
    d = _node_io.read_node(path)
    if d is None:
        return {
            'path': path,
            'id': os.path.basename(path).replace('.md', ''),
            'anchors': [], 'sem_links': [], 'embed_links': [],
            'impulse': '', 'summary': '', 'cleaned': '', 'impact': '',
            'source_base': '',
        }
    return {
        'path': path,
        'id': d['id'],
        'anchors': d['search_anchors'],
        'sem_links': d['semantic_links'],
        'embed_links': d['embed_links'],
        'impulse': d['impulse'],
        'summary': d['summary'],
        'cleaned': d['cleaned_data'],
        'impact': d['impact'],
        'source_base': d['source_base'],
    }


def load_index():
    node_index, anchor_index = {}, {}
    if not os.path.isdir(NODES_DIR):
        return node_index, anchor_index
    for fn in sorted(os.listdir(NODES_DIR)):
        if not fn.endswith('.md'):
            continue
        data = read_node(os.path.join(NODES_DIR, fn))
        node_index[data['id']] = data
        for a in data['anchors']:
            anchor_index.setdefault(a, []).append(data['id'])
    return node_index, anchor_index


def load_reverse(include_embed=False):
    """Load reverse links {target: [sources]} from reverse_index.json."""
    path = os.path.join(BASE, '..', 'reverse_index.json')
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    rev = dict(data.get('reverse', {}))
    if include_embed:
        for tgt, srcs in data.get('embed_reverse', {}).items():
            rev.setdefault(tgt, []).extend(srcs)
    return rev


mcp = FastMCP('spine-memory')


@mcp.tool()
def spine_list_nodes() -> list[str]:
    """Return the ids of all SPINE nodes in the graph."""
    node_index, _ = load_index()
    return sorted(node_index.keys())


@mcp.tool()
def spine_wander(start: str, hops: int = 2, include_embed: bool = False) -> list[dict]:
    """Walk the graph from a node (or anchor) and return impulse chain."""
    node_index, anchor_index = load_index()

    current = start
    if start not in node_index and start in anchor_index:
        current = anchor_index[start][0]
    if current not in node_index:
        return [{'error': f'node or anchor not found: {start}'}]

    visited = []
    queue = [(current, 0)]
    seen = set()
    while queue:
        nid, depth = queue.pop(0)
        if nid in seen or depth > hops:
            continue
        seen.add(nid)
        data = node_index.get(nid)
        if not data:
            continue
        visited.append({'id': nid, 'depth': depth, 'impulse': data['impulse']})
        links = list(data['sem_links'])
        if include_embed:
            links += data.get('embed_links', [])
        links = list(dict.fromkeys(links))
        for link in links:
            if link in node_index and link not in seen:
                queue.append((link, depth + 1))
    return visited


@mcp.tool()
def spine_read_node(node_id: str, layer: str = 'summary') -> str:
    """Read one layer of a node: impulse|summary|cleaned|impact|source_base."""
    node_index, _ = load_index()
    data = node_index.get(node_id)
    if not data:
        return f'node not found: {node_id}'
    if layer not in LAYERS:
        return f'unknown layer: {layer}. Use one of: {", ".join(LAYERS)}'
    return data[layer]


@mcp.tool()
def spine_search_anchors(anchor: str) -> list[str]:
    """Return node ids matching an anchor."""
    _, anchor_index = load_index()
    return anchor_index.get(anchor, [])


@mcp.tool()
def spine_backlinks(node_id: str, include_embed: bool = False) -> list[str]:
    """Return node ids that link to the given node (from reverse_index.json)."""
    return load_reverse(include_embed).get(node_id, [])


@mcp.tool()
def spine_for_file(filepath: str) -> list[dict]:
    """Return SPINE nodes (ADR/post-mortem/gotcha) linked to a code file."""
    path = os.path.join(BASE, '..', 'reverse_index.json')
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    code_index = data.get('code_index', {})
    hits = set()
    for fp, nids in code_index.items():
        if fp == filepath or fp.endswith(filepath) or filepath.endswith(fp):
            hits.update(nids)
    node_index, _ = load_index()
    return [{'id': n, 'impulse': node_index.get(n, {}).get('impulse', '')}
            for n in sorted(hits)]


@mcp.resource('spine://nodes/{node_id}')
def get_node(node_id: str) -> str:
    """Full markdown of a single node."""
    node_index, _ = load_index()
    data = node_index.get(node_id)
    if not data:
        return f'node not found: {node_id}'
    with open(data['path'], 'r', encoding='utf-8') as f:
        return f.read()


@mcp.resource('spine://methodology')
def get_methodology() -> str:
    """The SPINE methodology specification (EN)."""
    if os.path.exists(METHODOLOGY_EN):
        with open(METHODOLOGY_EN, 'r', encoding='utf-8') as f:
            return f.read()
    return 'methodology not found'


if __name__ == '__main__':
    mcp.run()
