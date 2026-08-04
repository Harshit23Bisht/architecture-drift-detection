import os
from typing import Dict, Any
from anthropic import Anthropic, APIError

class LLMExplainer:
    def __init__(self):
        # Initializes the client if the ANTHROPIC_API_KEY environment variable is present
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=self.api_key) if self.api_key else None

    def explain_violation(self, violation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls the Anthropic Claude API to generate a plain-language explanation and fix.
        """
        if not self.client:
            violation["ai_explanation"] = "LLM API key not found. Please set ANTHROPIC_API_KEY."
            violation["ai_fix"] = "Manual code review required to resolve this issue."
            return violation

        prompt = (
            f"You are an expert Python software architect. I have detected an architectural "
            f"violation in my codebase. \n"
            f"Violation Type: {violation.get('violation_type')}\n"
            f"Rule Broken: {violation.get('rule_broken')}\n"
            f"Involved Modules: {violation.get('edge_or_cycle')}\n\n"
            f"Provide two short, distinct paragraphs:\n"
            f"1. Explain why this is bad practice (under 50 words).\n"
            f"2. Recommend a concrete fix or refactoring strategy (under 50 words)."
        )

        try:
            # Using Claude 3 Haiku for the fastest, most cost-effective MVP response
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text
            parts = response_text.split("\n\n")
            
            violation["ai_explanation"] = parts[0] if len(parts) > 0 else response_text
            violation["ai_fix"] = parts[1] if len(parts) > 1 else "Implement standard separation of concerns."
            
        except APIError as e:
            violation["ai_explanation"] = f"Failed to contact LLM: {str(e)}"
            violation["ai_fix"] = "N/A"
            
        return violation