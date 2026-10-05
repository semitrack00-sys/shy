from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Sequence


@dataclass(frozen=True)
class EntityNode:
    entity_id: str
    name: str
    entity_type: str
    scope_id: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelationEdge:
    source_id: str
    target_id: str
    relation: str
    confidence: float
    provenance_ids: tuple[str, ...]


@dataclass(frozen=True)
class GraphSnapshot:
    nodes: tuple[EntityNode, ...]
    edges: tuple[RelationEdge, ...]
    truncated_nodes: bool
    truncated_edges: bool


@dataclass(frozen=True)
class GraphBuildResult:
    accepted: bool
    graph: GraphSnapshot | None
    reason: str | None


def _clean(value: str, max_chars: int = 500) -> str:
    return " ".join(str(value or "").strip().split())[:max_chars]


def build_graph(
    nodes: Sequence[EntityNode],
    edges: Sequence[RelationEdge],
    *,
    max_nodes: int = 200,
    max_edges: int = 500,
) -> GraphBuildResult:
    node_bound=max(1,min(int(max_nodes),1000))
    edge_bound=max(1,min(int(max_edges),2000))
    selected_nodes=tuple(nodes[:node_bound])
    selected_edges=tuple(edges[:edge_bound])

    ids:set[str]=set()
    scope_ids:set[str]=set()
    clean_nodes:list[EntityNode]=[]
    for node in selected_nodes:
        entity_id=_clean(node.entity_id,200)
        name=_clean(node.name,300)
        entity_type=_clean(node.entity_type,120)
        scope_id=_clean(node.scope_id,200)
        if not entity_id or not name or not entity_type or not scope_id:
            return GraphBuildResult(False,None,"invalid_entity_node")
        if entity_id in ids:
            return GraphBuildResult(False,None,"duplicate_entity_id")
        ids.add(entity_id); scope_ids.add(scope_id)
        clean_nodes.append(EntityNode(entity_id,name,entity_type,scope_id,tuple(_clean(a,200) for a in node.aliases if _clean(a,200))))

    if len(scope_ids)>1:
        return GraphBuildResult(False,None,"cross_scope_nodes_denied")

    clean_edges:list[RelationEdge]=[]
    for edge in selected_edges:
        source=_clean(edge.source_id,200); target=_clean(edge.target_id,200); relation=_clean(edge.relation,120)
        if source not in ids or target not in ids:
            return GraphBuildResult(False,None,"edge_references_unknown_entity")
        if not relation:
            return GraphBuildResult(False,None,"relation_required")
        provenance=tuple(_clean(p,240) for p in edge.provenance_ids if _clean(p,240))
        if not provenance:
            return GraphBuildResult(False,None,"relationship_provenance_required")
        clean_edges.append(RelationEdge(source,target,relation,round(max(0.0,min(1.0,float(edge.confidence))),6),provenance))

    return GraphBuildResult(
        True,
        GraphSnapshot(tuple(clean_nodes),tuple(clean_edges),len(nodes)>node_bound,len(edges)>edge_bound),
        None,
    )


def link_entity_mentions(text: str, graph: GraphSnapshot, *, max_matches: int = 20) -> tuple[EntityNode,...]:
    lowered=f" {_clean(text,12000).lower()} "
    matches:list[EntityNode]=[]
    for node in graph.nodes:
        names=(node.name,)+node.aliases
        if any(f" {name.lower()} " in lowered or lowered.strip()==name.lower() for name in names if name):
            matches.append(node)
    return tuple(matches[:max(1,min(int(max_matches),100))])


def neighbor_subgraph(
    graph: GraphSnapshot,
    entity_id: str,
    *,
    depth: int = 1,
    max_results: int = 30,
) -> GraphSnapshot:
    target=_clean(entity_id,200)
    node_map={n.entity_id:n for n in graph.nodes}
    if target not in node_map:
        return GraphSnapshot((),(),False,False)

    depth=max(0,min(int(depth),3))
    limit=max(1,min(int(max_results),100))
    visited={target}
    queue=deque([(target,0)])
    selected_edges:list[RelationEdge]=[]

    while queue and len(visited)<limit:
        current,d=queue.popleft()
        if d>=depth: continue
        for edge in graph.edges:
            neighbor=None
            if edge.source_id==current: neighbor=edge.target_id
            elif edge.target_id==current: neighbor=edge.source_id
            if neighbor is None: continue
            if edge not in selected_edges: selected_edges.append(edge)
            if neighbor not in visited and len(visited)<limit:
                visited.add(neighbor); queue.append((neighbor,d+1))

    nodes=tuple(node_map[i] for i in sorted(visited) if i in node_map)
    allowed=set(n.entity_id for n in nodes)
    edges=tuple(e for e in selected_edges if e.source_id in allowed and e.target_id in allowed)
    return GraphSnapshot(nodes,edges,False,False)


def public_graph(graph: GraphSnapshot) -> dict[str, object]:
    return {
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "truncated_nodes": graph.truncated_nodes,
        "truncated_edges": graph.truncated_edges,
        "nodes":[{"entity_id":n.entity_id,"name":n.name,"entity_type":n.entity_type,"scope_id":n.scope_id} for n in graph.nodes],
        "edges":[{"source_id":e.source_id,"target_id":e.target_id,"relation":e.relation,"confidence":e.confidence,"provenance_count":len(e.provenance_ids)} for e in graph.edges],
    }
