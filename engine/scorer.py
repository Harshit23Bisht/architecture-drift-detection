from typing import Dict, Any

class SeverityScorer:
    @staticmethod
    def score_violation(violation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attaches a severity label ('high', 'medium', 'low') and an impact score (0-100)
        to a violation dictionary based on internal rubrics.
        """
        v_type = violation.get("violation_type")
        
        if v_type == "layer_violation":
            # Layer skips are major architectural breaches
            violation["severity"] = "high"
            violation["impact_score"] = 85
            
        elif v_type == "circular_dependency":
            # Weight cycles by length: direct coupling vs complex loops
            cycle_length = len(violation.get("edge_or_cycle", []))
            if cycle_length > 2:
                violation["severity"] = "high"
                violation["impact_score"] = 90
            else:
                violation["severity"] = "medium"
                violation["impact_score"] = 60
                
        else:
            violation["severity"] = "low"
            violation["impact_score"] = 20
            
        return violation