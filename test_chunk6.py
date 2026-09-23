from engine.learned_scorer import LearnedSeverityScorer

scorer = LearnedSeverityScorer()

test_cases = [
    {
        "name": "Synthetic Layer Breach (Controller -> Repository)",
        "violation": {"type": "layer_violation", "layers_skipped": 2, "fan_out": 3}
    },
    {
        "name": "Tight 2-Node Circular Dependency",
        "violation": {"type": "circular_dependency", "cycle_length": 2, "fan_out": 2}
    },
    {
        "name": "Self-Import Coupling",
        "violation": {"type": "self_dependency", "cycle_length": 0, "fan_out": 1}
    }
]

print("=== Chunk 6: Learned Severity Scorer Benchmark ===")
for case in test_cases:
    result = scorer.predict_severity(case["violation"])
    print(f"\nDefect: {case['name']}")
    print(f"  Predicted Tier: {result['predicted_severity']}")
    print(f"  Confidence:     {result['confidence'] * 100:.1f}%")
    print(f"  Health Impact:  -{result['impact_deduction']} pts")