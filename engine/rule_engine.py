import networkx as nx
from typing import List, Dict, Any

class RuleEngine:
    def __init__(self, configured_layers: List[Any]):
        """
        Initializes the engine with the LayerRule objects validated in Chunk 1.
        """
        self.layers = configured_layers
        self.allowed_map = {layer.name: layer.allowed_calls for layer in self.layers}

    def _get_layer_for_module(self, module_name: str) -> str | None:
        """
        Determines which layer a module belongs to based on its name.
        Uses a simple substring match for the MVP (e.g., 'myapp.controllers.user' -> 'Controller').
        """
        mod_lower = module_name.lower()
        for layer in self.layers:
            # Match the layer name (case-insensitive) against the module path
            if layer.name.lower() in mod_lower:
                return layer.name
        return None

    def detect_violations(self, graph: nx.DiGraph) -> List[Dict[str, Any]]:
        """
        Scans the graph for layer violations and circular dependencies, formatting
        the results into structured dictionaries[cite: 2].
        """
        violations = []

        # 1. Detect Layer Violations
        for source, target in graph.edges():
            source_layer = self._get_layer_for_module(source)
            target_layer = self._get_layer_for_module(target)

            # We only evaluate edges where both nodes belong to recognized internal layers
            if source_layer and target_layer and source_layer != target_layer:
                allowed_targets = self.allowed_map.get(source_layer, [])
                
                # Check if the target is permitted (and handle wildcard '*' if you support it)
                if target_layer not in allowed_targets and "*" not in allowed_targets:
                    violations.append({
                        "rule_broken": f"Layer '{source_layer}' is not allowed to call '{target_layer}'",
                        "edge_or_cycle": [source, target],
                        "violation_type": "layer_violation"
                    })

        # 2. Detect Circular Dependencies
        # nx.simple_cycles finds all elementary circuits in a directed graph[cite: 2]
        cycles = list(nx.simple_cycles(graph))
        for cycle in cycles:
            # We typically only care about cycles involving more than one distinct module
            if len(cycle) > 1:
                # To prevent duplicates from simple_cycles (e.g., A->B->A and B->A->B),
                # we could normalize the cycle list, but NetworkX simple_cycles already 
                # returns unique cycles based on combinations.
                violations.append({
                    "rule_broken": "Circular dependency detected",
                    "edge_or_cycle": cycle,
                    "violation_type": "circular_dependency"
                })

        return violations