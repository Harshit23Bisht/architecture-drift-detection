import networkx as nx
from typing import List, Dict, Any

class RuleEngine:
    def __init__(self, configured_layers: List[Any]):
        """
        Initializes the engine with the LayerRule objects.
        """
        self.layers = configured_layers
        self.allowed_map = {layer.name: getattr(layer, 'allowed_calls', []) for layer in self.layers}
        self.forbidden_map = {layer.name: getattr(layer, 'forbidden_calls', []) for layer in self.layers}

    def _get_layer_for_module(self, module_name: str) -> str | None:
        """
        Determines which layer a module belongs to based on exact package/path segment matching.
        Eliminates unsafe substring matching to avoid false positives (e.g., 'controller_helper' matching 'Controller').
        """
        if not module_name:
            return None

        # Replace path separators and split into package/file segments
        cleaned_path = module_name.replace('/', '.').replace('\\', '.')
        parts = [p.lower() for p in cleaned_path.split('.') if p]

        for layer in self.layers:
            lname = layer.name.lower()
            # Match exact segment or standard plural/singular variant (e.g., 'controllers' <-> 'Controller')
            for part in parts:
                if part == lname or part == lname + "s" or lname == part + "s":
                    return layer.name

        return None

    def detect_violations(self, graph: nx.DiGraph, edge_metadata: Dict = None) -> List[Dict[str, Any]]:
        """
        Scans the graph for layer violations and circular dependencies, formatting
        the results into structured dictionaries without duplicate violations.
        """
        violations = []
        seen_violations = set()
        violation_counter = 1

        # 1. Detect Layer Violations
        for source, target in graph.edges():
            source_layer = self._get_layer_for_module(source)
            target_layer = self._get_layer_for_module(target)

            # Retrieve location metadata if present in graph edge or metadata lookup
            edge_data = graph.get_edge_data(source, target) or {}
            line = edge_data.get("line")
            if not line and edge_metadata:
                line = edge_metadata.get((source, target), {}).get("line")

            # We only evaluate edges where both nodes belong to recognized internal layers
            if source_layer and target_layer and source_layer != target_layer:
                allowed_targets = self.allowed_map.get(source_layer, [])
                forbidden_targets = self.forbidden_map.get(source_layer, [])

                is_forbidden = (target_layer in forbidden_targets or "*" in forbidden_targets)
                is_allowed = (target_layer in allowed_targets or "*" in allowed_targets)

                # Explicit forbidden call check
                if is_forbidden:
                    v_key = (source, target, "forbidden_call")
                    if v_key not in seen_violations:
                        seen_violations.add(v_key)
                        violations.append({
                            "violation_id": f"V-{violation_counter}",
                            "rule_broken": f"Forbidden call: Layer '{source_layer}' is explicitly forbidden to call '{target_layer}'",
                            "edge_or_cycle": [source, target],
                            "source": source,
                            "target": target,
                            "source_layer": source_layer,
                            "target_layer": target_layer,
                            "line": line,
                            "violation_type": "layer_violation"
                        })
                        violation_counter += 1

                # Disallowed call check
                elif not is_allowed:
                    v_key = (source, target, "layer_violation")
                    if v_key not in seen_violations:
                        seen_violations.add(v_key)
                        violations.append({
                            "violation_id": f"V-{violation_counter}",
                            "rule_broken": f"Layer '{source_layer}' is not allowed to call '{target_layer}'",
                            "edge_or_cycle": [source, target],
                            "source": source,
                            "target": target,
                            "source_layer": source_layer,
                            "target_layer": target_layer,
                            "line": line,
                            "violation_type": "layer_violation"
                        })
                        violation_counter += 1

        # 2. Detect Circular Dependencies
        try:
            cycles = list(nx.simple_cycles(graph))
        except Exception:
            cycles = []

        for cycle in cycles:
            if len(cycle) > 1:
                normalized_cycle = tuple(sorted(cycle))
                v_key = (normalized_cycle, "circular_dependency")
                if v_key not in seen_violations:
                    seen_violations.add(v_key)
                    violations.append({
                        "violation_id": f"V-{violation_counter}",
                        "rule_broken": "Circular dependency detected",
                        "edge_or_cycle": cycle,
                        "violation_type": "circular_dependency"
                    })
                    violation_counter += 1

        return violations
