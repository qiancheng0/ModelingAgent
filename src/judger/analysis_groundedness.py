import json
import ast
import os
from openai import OpenAI

class AnalysisGroundednessJudger:
    SYS_PROMPT = """You are currently evaluating mathematical modeling papers. Your task is to assess how well the solution's analysis is grounded in mathematical and scientific principles. You should evaluate based on the role you are given.

Score each aspect from 0-1, starting at 0 and requiring justification for any increase:

1. Analytical Depth (0-1):
   0.00: No meaningful analysis
        Example: Superficial observations without reasoning
   0.25: Basic analysis
        Example: Simple descriptive analysis without connections
   0.50: Standard analysis
        Example: Clear reasoning with some depth
   0.75: Advanced analysis
        Example: Deep insights with strong connections
   1.00: Exceptional analysis
        Example: Novel insights with comprehensive reasoning

2. Mathematical Rigor (0-1):
   0.00: No mathematical support
        Example: Claims without mathematical backing
   0.25: Basic mathematics
        Example: Simple calculations without justification
   0.50: Standard rigor
        Example: Clear mathematical reasoning
   0.75: Strong rigor
        Example: Detailed proofs and derivations
   1.00: Exceptional rigor
        Example: Complete mathematical framework

3. Results Interpretation (0-1):
   0.00: No interpretation
        Example: Raw results without context
   0.25: Basic interpretation
        Example: Simple description of results
   0.50: Clear interpretation
        Example: Results explained with context
   0.75: Thorough interpretation
        Example: Deep analysis of implications
   1.00: Exceptional interpretation
        Example: Comprehensive analysis with insights

4. Critical Analysis (0-1):
   0.00: No critical thinking
        Example: Accepts all results without question
   0.25: Basic criticism
        Example: Notes obvious limitations
   0.50: Standard analysis
        Example: Identifies key strengths/weaknesses
   0.75: Strong analysis
        Example: Deep examination of assumptions
   1.00: Exceptional analysis
        Example: Comprehensive critique with alternatives

5. Future Implications (0-1):
   0.00: No discussion
        Example: Ends at results
   0.25: Basic implications
        Example: Simple next steps
   0.50: Clear implications
        Example: Reasonable future directions
   0.75: Strong implications
        Example: Detailed future research paths
   1.00: Exceptional vision
        Example: Novel research directions with justification

---

Your response must follow this exact format:

Your Response:
```json
{
    "analytical_depth": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "mathematical_rigor": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "results_interpretation": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "critical_analysis": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "future_implications": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "overall_score": 0.0,
    "overall_feedback": "Critical analysis of strengths and weaknesses"
}
```

---

Note: Scores must be exactly 0.00, 0.25, 0.50, 0.75, or 1.00. Start at 0 and justify each increment. Be extremely critical. You should also give your score and explaination from your role's perspective."""

    USER_PROMPT = """Please evaluate the analysis groundedness of the following mathematical modeling paper:

{writing}

Provide scores and detailed justification for each aspect. Remember your role as {role_name}. Your judgement should be based on this role's perspective.

Your Response:
"""

    def __init__(self):
        if os.path.exists("../../secret.json"):
            secret = json.load(open("../../secret.json"))
            self.client = OpenAI(api_key=secret["api_key"], base_url=secret["base_url"])
        else:
            self.client = OpenAI(api_key="sk-...")

    def run(self, writing: str, role: dict = None) -> dict:
        role_name = role["name"].strip()
        role_details = role["details"].strip()
        messages = [
            {'role': 'system', 'content': role_details + "\n\n" + self.SYS_PROMPT},
            {'role': 'user', 'content': self.USER_PROMPT.format(writing=writing, role_name=role_name)}
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
        
        scores = [result[aspect]["score"] for aspect in [
            "analytical_depth", "mathematical_rigor", "results_interpretation", 
            "critical_analysis", "future_implications"
        ]]
        result["calculated_overall"] = sum(scores) / len(scores)
        result["role"] = role
        return result