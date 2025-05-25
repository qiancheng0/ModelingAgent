import json
import ast
import os
from openai import OpenAI

class InnovativenessJudger:
    SYS_PROMPT = """You are currently evaluating mathematical modeling papers. Your task is to assess the innovativeness and originality of the solution approach. You should evaluate based on the role you are given.

Score each aspect from 0-1, starting at 0 and requiring justification for any increase:

1. Methodological Innovation (0-1):
   0.00: Standard/textbook approach
        Example: Using basic linear regression without modification
   0.25: Minor adaptations
        Example: Small tweaks to existing methods
   0.50: Meaningful modifications
        Example: Significant adaptations to standard approaches
   0.75: Novel combinations
        Example: Creative synthesis of multiple methods
   1.00: Groundbreaking approach
        Example: Entirely new methodology with strong justification

2. Problem Framing (0-1):
   0.00: Conventional perspective
        Example: Following typical problem formulation
   0.25: Slight reframing
        Example: Minor changes to standard approach
   0.50: Fresh perspective
        Example: New angle on known problem
   0.75: Novel framing
        Example: Unique problem decomposition
   1.00: Revolutionary perspective
        Example: Paradigm-shifting problem formulation

3. Solution Creativity (0-1):
   0.00: Standard solution
        Example: Direct application of known methods
   0.25: Minor creativity
        Example: Small creative elements in standard approach
   0.50: Notable creativity
        Example: Original elements in key areas
   0.75: Significant creativity
        Example: Multiple creative components
   1.00: Exceptional creativity
        Example: Entirely novel solution approach

4. Technical Advancement (0-1):
   0.00: No advancement
        Example: Uses only existing techniques
   0.25: Minor improvements
        Example: Small technical optimizations
   0.50: Meaningful advances
        Example: New technical contributions
   0.75: Significant advances
        Example: Multiple technical innovations
   1.00: Major breakthrough
        Example: Revolutionary technical approach

5. Impact Potential (0-1):
   0.00: Minimal impact
        Example: No new insights or applications
   0.25: Limited impact
        Example: Minor improvements to existing methods
   0.50: Moderate impact
        Example: Useful new approach for specific cases
   0.75: High impact
        Example: Broadly applicable new methods
   1.00: Transformative
        Example: Could change the field significantly

---

Your response must follow this exact format:

Your Response:
```json
{
    "methodological_innovation": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "problem_framing": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "solution_creativity": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "technical_advancement": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "impact_potential": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "overall_score": 0.0,
    "overall_feedback": "Critical analysis of innovative aspects and potential impact"
}
```

---

Note: Scores must be exactly 0.00, 0.25, 0.50, 0.75, or 1.00. Start at 0 and justify each increment. Be extremely critical - true innovation is rare. You should also give your score and explaination from your role's perspective."""

    USER_PROMPT = """Please evaluate the innovativeness of the following mathematical modeling paper:

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
        result =  ast.literal_eval(json_str) 
        
        scores = [result[aspect]["score"] for aspect in [
            "methodological_innovation", "problem_framing", "solution_creativity", 
            "technical_advancement", "impact_potential"
        ]]
        result["calculated_overall"] = sum(scores) / len(scores)
        result["role"] = role
        return result