import numpy as np
from typing import Dict, Any, List, Optional
from sklearn.ensemble import RandomForestClassifier

class LearnedSeverityScorer:
    """
    ML-based violation severity classifier using RandomForest.
    Extracts structural graph features and classifies violations into HIGH, MEDIUM, or LOW tiers
    with confidence scores and Architecture Health Score impact penalties.
    """

    SEVERITY_TIERS = ["LOW", "MEDIUM", "HIGH"]
    IMPACT_MAP = {
        "HIGH": 50,
        "MEDIUM": 25,
        "LOW": 10
    }

    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=50, random_state=42)
        self._train_baseline_model()

    def _train_baseline_model(self):
        """
        Trains baseline model on synthetic architectural violation patterns.
        Features: [rule_type_id, cycle_length, layers_skipped, fan_out, is_bidirectional]
        Rule Type IDs: 0: layer_violation, 1: circular_dependency, 2: forbidden_call
        """
        X_train = np.array([
            # Severe layer breaches (Controller skipping Service directly to DB/Repo)
            [0, 0, 3, 12, 0],
            [0, 0, 2, 8, 0],
            [0, 0, 4, 15, 0],
            # Tight circular dependency cycles (2-3 nodes, bidirectional coupling)
            [1, 2, 0, 4, 1],
            [1, 2, 0, 1, 1],
            [1, 3, 0, 3, 1],
            # Loose circular dependency cycles (longer paths, 5+ hops)
            [1, 6, 0, 2, 0],
            [1, 5, 0, 3, 0],
            # Minor single-layer skips or low fan-out calls
            [0, 0, 1, 1, 0],
            [0, 0, 1, 2, 0],
            [2, 0, 0, 1, 0],
            [2, 0, 0, 2, 0]
        ])

        # Labels: 0 = LOW, 1 = MEDIUM, 2 = HIGH
        y_train = np.array([
            2, 2, 2, # Severe layer breaches -> HIGH
            1, 1, 1, # Tight cycles -> MEDIUM
            0, 0,    # Loose cycles -> LOW
            0, 0,    # Minor layer skips -> LOW
            0, 0     # Single forbidden calls -> LOW
        ])

        self.model.fit(X_train, y_train)

    def extract_features(self, violation: Dict[str, Any], graph=None) -> np.ndarray:
        """
        Extracts numerical features from violation metadata and graph structure.
        """
        v_type = violation.get("violation_type", "layer_violation")
        if v_type == "circular_dependency":
            rule_id = 1
        elif v_type == "forbidden_call":
            rule_id = 2
        else:
            rule_id = 0

        cycle = violation.get("cycle", violation.get("edge_or_cycle", []))
        unique_cycle_nodes = set(cycle) if isinstance(cycle, list) else set()
        
        # Effective cycle length: number of unique nodes in cycle
        cycle_len = len(unique_cycle_nodes) if unique_cycle_nodes else 0

        # Estimate layers skipped
        layers_skipped = violation.get("layers_skipped", 1 if rule_id == 0 else 0)

        # Infer bidirectional and fan-out
        source_module = violation.get("source") or (cycle[0] if cycle else "")
        target_module = violation.get("target") or (cycle[1] if len(cycle) > 1 else "")

        fan_out = 1
        # Tight 2-node cycle (A -> B -> A) is bidirectional coupling
        is_bidirectional = 1 if (rule_id == 1 and cycle_len == 2) else 0

        if graph is not None and source_module and source_module in graph:
            fan_out = graph.out_degree(source_module)
            if target_module and graph.has_edge(target_module, source_module):
                is_bidirectional = 1

        return np.array([[rule_id, cycle_len, layers_skipped, fan_out, is_bidirectional]])

    def score_violation(self, violation: Dict[str, Any], graph=None) -> Dict[str, Any]:
        """
        Scores a single violation using the trained model.
        """
        features = self.extract_features(violation, graph)
        pred_idx = self.model.predict(features)[0]
        probabilities = self.model.predict_proba(features)[0]
        confidence = float(np.max(probabilities))

        predicted_severity = self.SEVERITY_TIERS[pred_idx]
        impact = self.IMPACT_MAP.get(predicted_severity, 15)

        scored = dict(violation)
        scored["severity"] = predicted_severity.lower()
        scored["predicted_tier"] = predicted_severity
        scored["confidence"] = round(confidence, 2)
        scored["impact_score"] = impact

        return scored
