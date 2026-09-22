import numpy as np
from typing import Dict, Any, List
from sklearn.ensemble import RandomForestClassifier

class LearnedSeverityScorer:
    """
    Learned Severity Scorer (Chunk 6)
    Replaces or complements rule-based heuristics with a trained classifier.
    """

    LABEL_MAP = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}
    REV_LABEL_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=20, random_state=42)
        self.is_trained = False
        self._train_baseline_model()

    def _extract_features(self, violation: Dict[str, Any]) -> List[float]:
        """Vectorizes a violation object into a numerical feature vector."""
        v_type = violation.get("type", "").lower()
        if "layer" in v_type or "skip" in v_type:
            rule_code = 0
        elif "self" in v_type:
            rule_code = 1
        elif "cycle" in v_type or "circular" in v_type:
            rule_code = 2
        else:
            rule_code = 3

        cycle_len = float(violation.get("cycle_length", 0))
        layers_skipped = float(violation.get("layers_skipped", 1 if rule_code == 0 else 0))
        caller_fan_out = float(violation.get("fan_out", 1))

        return [rule_code, cycle_len, layers_skipped, caller_fan_out]

    def _train_baseline_model(self):
        """Trains the model on labeled architectural violation archetypes."""
        # Features: [rule_code, cycle_len, layers_skipped, fan_out]
        X = np.array([
            # Layer bypasses -> HIGH (2)
            [0, 0, 1, 2],
            [0, 0, 2, 4],
            [0, 0, 3, 5],
            # Deep/multi-node cycles -> HIGH (2)
            [2, 3, 0, 3],
            [2, 4, 0, 4],
            # Tight 2-node cycles -> MEDIUM (1)
            [2, 2, 0, 2],
            # Self-dependencies & minor imports -> LOW (0)
            [1, 0, 0, 1],
            [1, 0, 0, 2],
            [3, 0, 0, 1]
        ])
        y = np.array([2, 2, 2, 2, 2, 1, 0, 0, 0])

        self.model.fit(X, y)
        self.is_trained = True

    def predict_severity(self, violation: Dict[str, Any]) -> Dict[str, Any]:
        """Predicts the severity class and confidence score for a violation."""
        feats = np.array([self._extract_features(violation)])
        pred_label_idx = self.model.predict(feats)[0]
        probabilities = self.model.predict_proba(feats)[0]

        severity = self.LABEL_MAP.get(pred_label_idx, "MEDIUM")
        confidence = float(probabilities[pred_label_idx])

        # Derive numerical impact point deduction based on predicted tier
        deductions = {"LOW": 10, "MEDIUM": 25, "HIGH": 50}
        impact = deductions.get(severity, 20)

        return {
            "predicted_severity": severity,
            "confidence": round(confidence, 2),
            "impact_deduction": impact,
            "scoring_mode": "ML-Learned"
        }