import networkx as nx
from typing import List, Dict, Any

class GraphBuilder:
    @staticmethod
    def build_from_edges(edges: List[Dict[str, str]]) -> nx.DiGraph:
        """
        Constructs a NetworkX directed graph from a list of edge dictionaries.
        Expected format: [{"source": "module_a", "target": "module_b"}, ...]
        """
        graph = nx.DiGraph()
        
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            
            if source and target:
                # NetworkX automatically adds nodes if they don't exist when an edge is added
                graph.add_edge(source, target)
                
        return graph