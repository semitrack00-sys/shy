import importlib.util,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"services"/"agent-runtime"/"entity_graph.py"
s=importlib.util.spec_from_file_location("g",P);g=importlib.util.module_from_spec(s);sys.modules["g"]=g;s.loader.exec_module(g)
def a(c,m):
    if not c: raise AssertionError(m)
nodes=(
 g.EntityNode("e1","Project Atlas","PROJECT","ws1",("Atlas",)),
 g.EntityNode("e2","PostgreSQL","DATABASE","ws1",("Postgres",)),
 g.EntityNode("e3","Strict Consistency","REQUIREMENT","ws1",()),
)
edges=(
 g.RelationEdge("e1","e2","USES",0.95,("k1",)),
 g.RelationEdge("e1","e3","REQUIRES",0.98,("k2",)),
)
r=g.build_graph(nodes,edges);a(r.accepted and r.graph is not None,r);print("graph build: PASS")
m=g.link_entity_mentions("Atlas uses Postgres",r.graph);a({x.entity_id for x in m}=={"e1","e2"},m);print("entity linking: PASS")
sub=g.neighbor_subgraph(r.graph,"e1",depth=1);a(len(sub.nodes)==3 and len(sub.edges)==2,sub);print("bounded neighbor traversal: PASS")
cross=g.build_graph((nodes[0],g.EntityNode("x","Other","PROJECT","ws2")),());a(not cross.accepted and cross.reason=="cross_scope_nodes_denied",cross);print("cross-scope denial: PASS")
noprov=g.build_graph(nodes,(g.RelationEdge("e1","e2","USES",0.8,()),));a(not noprov.accepted and noprov.reason=="relationship_provenance_required",noprov);print("relationship provenance: PASS")
bad=g.build_graph(nodes,(g.RelationEdge("e1","missing","USES",0.8,("k",)),));a(not bad.accepted and bad.reason=="edge_references_unknown_entity",bad);print("unknown entity edge rejection: PASS")
pub=g.public_graph(r.graph);a(pub["edges"][0]["provenance_count"]==1,pub);a("provenance_ids" not in pub["edges"][0],"private provenance ids");print("public graph metadata: PASS")
print("SHY v0.27 KNOWLEDGE GRAPH CHECKPOINT: PASS")
