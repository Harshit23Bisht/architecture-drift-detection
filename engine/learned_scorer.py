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
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self._train_baseline_model()

    def _train_baseline_model(self):
        """
        Trains baseline model on synthetic architectural violation patterns.
        Features: [rule_type_id, cycle_length, layers_skipped, fan_out, is_bidirectional]
        Rule Type IDs: 0: layer_violation, 1: circular_dependency, 2: other/forbidden/self
        """
        X_train = np.array([
            # Severe layer breaches (skipping 2+ layers, fan_out >= 2) -> HIGH
            [0, 0, 2, 3, 0],
            [0, 0, 3, 5, 0],
            [0, 0, 2, 8, 0],
            [0, 0, 4, 12, 0],
            [0, 0, 3, 2, 0],

            # Tight circular dependency cycles (cycle_length 2-3) -> MEDIUM
            [1, 2, 0, 2, 1],
            [1, 2, 0, 4, 1],
            [1, 2, 0, 1, 1],
            [1, 3, 0, 3, 1],
            [1, 3, 0, 2, 1],

            # Loose cycles (cycle_length >= 5) -> LOW
            [1, 6, 0, 2, 0],
            [1, 5, 0, 3, 0],

            # Minor layer breaches (skipping 1 layer, fan_out 1) -> LOW
            [0, 0, 1, 1, 0],

            # Self-import or low impact coupling -> LOW
            [2, 0, 0, 1, 0],
            [2, 0, 0, 2, 0],
            [2, 0, 0, 0, 0]
        ])

        # Labels: 0 = LOW, 1 = MEDIUM, 2 = HIGH
        y_train = np.array([
            2, 2, 2, 2, 2, # Layer breaches -> HIGH
            1, 1, 1, 1, 1, # Tight cycles -> MEDIUM
            0, 0,          # Loose cycles -> LOW
            0,             # Minor 1-layer skip -> LOW
            0, 0, 0        # Self-imports/calls -> LOW
        ])

        self.model.fit(X_train, y_train)

    def extract_features(self, violation: Dict[str, Any], graph=None) -> np.ndarray:
        """
        Extracts numerical features from violation metadata and graph structure.
        """
        raw_type = str(violation.get("type", violation.get("violation_type", "layer_violation"))).lower()
        if "circular" in raw_type or "cycle" in raw_type:
            rule_id = 1
        elif "layer" in raw_type:
            rule_id = 0
        else:
            rule_id = 2

        # Cycle length
        cycle = violation.get("cycle", violation.get("edge_or_cycle", []))
        if isinstance(cycle, list) and cycle:
            cycle_len = len(set(cycle))
        else:
            cycle_len = int(violation.get("cycle_length", 0))

        # Layers skipped
        layers_skipped = int(violation.get("layers_skipped", 2 if rule_id == 0 else 0))

        # Fan-out
        source_module = violation.get("source") or (cycle[0] if isinstance(cycle, list) and cycle else "")
        target_module = violation.get("target") or (cycle[1] if isinstance(cycle, list) and len(cycle) > 1 else "")

        fan_out = int(violation.get("fan_out", 1))
        is_bidirectional = 1 if (rule_id == 1 and cycle_len == 2) else 0

        if graph is not None and source_module and hasattr(graph, "out_degree") and source_module in graph:
            fan_out = graph.out_degree(source_module)
            if target_module and graph.has_edge(target_module, source_module):
                is_bidirectional = 1

        return np.array([[rule_id, cycle_len, layers_skipped, fan_out, is_bidirectional]])

    def score_violation(self, violation: Dict[str, Any], graph=None) -> Dict[str, Any]:
        """
        Scores a single violation using the trained model.
        Returns unified dictionary with all standard severity fields.
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
        scored["predicted_severity"] = predicted_severity
        scored["confidence"] = round(confidence, 2)
        scored["impact_score"] = impact
        scored["impact_deduction"] = impact
        scored["scoring_mode"] = "learned_rf"

        return scored

    def predict_severity(self, violation: Dict[str, Any], graph=None) -> Dict[str, Any]:
        """
        Alias for test_chunk6 and legacy callers.
        """
        return self.score_violation(violation, graph)
