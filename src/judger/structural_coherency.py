import json
import ast
import os
from openai import OpenAI

class StructuralCoherencyJudger:
    SYS_PROMPT = """You are an expert judge evaluating mathematical modeling papers. Your task is to assess the structural coherency of the paper by checking if it contains all necessary components.

Key components to evaluate (up to 1 point each):

1. Problem Restatement (0-1):
   0.00: Missing or completely misunderstood
        Example: Simply copying problem text or missing key elements
   0.25: Present but superficial
        Example: Basic bullet points of requirements without context
   0.50: Adequate but lacks depth
        Example: Covers main points but misses subtle relationships
   0.75: Good with minor gaps
        Example: Clear understanding but could elaborate connections
   1.00: Excellent and comprehensive
        Example: Deep understanding with clear relationships and context

2. Assumptions and Justification (0-1):
   0.00: Missing or unjustified
        Example: No assumptions listed or completely unreasonable ones
   0.25: Listed but poorly justified
        Example: "We assume linear relationship" without explanation
   0.50: Reasonable but incomplete
        Example: Key assumptions stated but some justifications weak
   0.75: Well-justified with minor gaps
        Example: Clear justifications but missing some implications
   1.00: Comprehensive and thorough
        Example: All assumptions clearly stated, justified, and impacts explained

3. Modeling Implementation (0-1):
   0.00: Missing or fundamentally flawed
        Example: No clear mathematical formulation
   0.25: Basic but poorly developed
        Example: Equations listed without explanation or context
   0.50: Sound but lacks rigor
        Example: Correct approach but missing some derivations
   0.75: Strong with minor omissions
        Example: Clear formulation but could be more detailed
   1.00: Rigorous and complete
        Example: Clear, justified, and thorough mathematical development

4. Solution Process (0-1):
   0.00: Missing or invalid
        Example: No solution method or completely incorrect approach
   0.25: Vague or incomplete
        Example: "We solved using computer" without details
   0.50: Basic but workable
        Example: Solution steps listed but lacking validation
   0.75: Clear with minor gaps
        Example: Well-documented but missing some error analysis
   1.00: Comprehensive and validated
        Example: Clear steps, validation, and error analysis

5. Analysis (0-1):
   0.00: Missing or invalid
        Example: No analysis or completely wrong interpretations
   0.25: Superficial discussion
        Example: Basic statements without supporting evidence
   0.50: Valid but limited
        Example: Correct analysis but missing sensitivity tests
   0.75: Thorough with minor gaps
        Example: Good analysis but could explore more implications
   1.00: Deep and insightful
        Example: Comprehensive analysis with validation and implications

---

Your response must follow this exact format:

Your Response:
```json
{
    "scores": {
        "problem_restatement": 0.0,
        "assumptions": 0.0,
        "modeling_implementation": 0.0,
        "solution_process": 0.0,
        "analysis": 0.0
    },
    "explanation": {
        "problem_restatement": "why this score",
        "assumptions": "why this score",
        "modeling_implementation": "why this score",
        "solution_process": "why this score",
        "analysis": "why this score"
    }
}
```

---

Note: For each component, score must be exactly 0.0, 0.25, 0.50, 0.75, or 1.00. Be extremely critical - most solutions should score in the 0.25-0.50 range unless truly exceptional."""

    USER_PROMPT = """Please evaluate the structural coherency of the following mathematical modeling paper:

{writing}

Provide scores and explanations for each component.

Your Response:
"""

    def __init__(self):
        if os.path.exists("../../secret.json"):
            secret = json.load(open("../../secret.json"))
            self.client = OpenAI(api_key=secret["api_key"], base_url=secret["base_url"])
        else:
            self.client = OpenAI(api_key="sk-...")

    def run(self, writing: str) -> dict:
        messages = [
            {'role': 'system', 'content': self.SYS_PROMPT},
            {'role': 'user', 'content': self.USER_PROMPT.format(writing=writing)}
        ]

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.0,
            n=1,
        )
        
        content = response.choices[0].message.content
        json_str = content.split("```json")[1].split("```")[0].strip()
        result = ast.literal_eval(json_str)
        total_score = sum(result["scores"].values())
        result["total_score"] = total_score
        average_score = total_score / len(result["scores"])
        result["calculated_overall"] = average_score
        
        return result 