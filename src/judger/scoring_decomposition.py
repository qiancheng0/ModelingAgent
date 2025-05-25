import json
import ast
import os
from openai import OpenAI

class ScoringDecompositionJudger:
    SYS_PROMPT = """You are an expert judge evaluating mathematical modeling papers. Your task is to assess if each requirement of the problem is faithfully fulfilled based on the provided grading points.

For each grading point, score from 0-1:

0.00: Requirement Ignored/Failed
      Example: No attempt to address the requirement
      Example: Completely incorrect approach

0.25: Minimal/Poor Treatment
      Example: Superficial mention without proper implementation
      Example: Major flaws in approach or understanding

0.50: Partial/Basic Treatment
      Example: Addresses main points but misses important aspects
      Example: Correct approach but incomplete implementation

0.75: Good but Not Perfect
      Example: Strong treatment with minor omissions
      Example: Well-implemented but could be more thorough

1.00: Complete and Excellent
      Example: Comprehensive treatment of all aspects
      Example: Thorough implementation with validation

Critical Evaluation Points:

1. Completeness:
   - Every sub-requirement must be explicitly addressed
   - Partial treatment results in significant score reduction
   - Missing elements cannot be compensated by other strengths

2. Quality of Implementation:
   - Mathematical rigor is essential
   - Must show clear methodology
   - Must include validation
   - Surface-level solutions score 0.25 maximum

3. Integration:
   - Requirements must work together coherently
   - Interdependencies must be addressed
   - Isolated solutions score 0.50 maximum

4. Validation:
   - Results must be verified
   - Assumptions must be tested
   - No validation means 0.25 maximum score

---

Your response must follow this exact format:

Your Response:
```json
{
    "scores": {
        "grading_point_1": 0.0,
        "grading_point_2": 0.0,
        ...
    },
    "explanation": {
        "grading_point_1": "why this score",
        "grading_point_2": "why this score",
        ...
    }
}
```

---

Note: For each grading point, score must be exactly 0.0, 0.25, 0.50, 0.75, or 1.00. Use the grading point's category as the key in the scores and explanation dictionaries. Be extremely critical - most solutions should score in the 0.25-0.50 range unless truly exceptional."""

    USER_PROMPT = """Please evaluate if the following mathematical modeling paper fulfills each grading point requirement:

Paper Content:
{writing}

---

Grading Points to Evaluate:
{grading_points}

---

Provide scores and explanations for each grading point.

Your Response:
"""

    def __init__(self):
        if os.path.exists("../../secret.json"):
            secret = json.load(open("../../secret.json"))
            self.client = OpenAI(api_key=secret["api_key"], base_url=secret["base_url"])
        else:
            self.client = OpenAI(api_key="sk-...")

    def run(self, writing: str, grading_points: list) -> dict:
        messages = [
            {'role': 'system', 'content': self.SYS_PROMPT},
            {'role': 'user', 'content': self.USER_PROMPT.format(
                writing=writing,
                grading_points=json.dumps(grading_points, indent=2)
            )}
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