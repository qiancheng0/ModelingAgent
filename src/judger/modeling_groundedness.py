import json
import ast
import os
from openai import OpenAI

class ModelingGroundednessJudger:
     SYS_PROMPT = """You are currently evaluating mathematical modeling papers. Your task is to assess how well the solution's modeling approach is grounded in mathematical and scientific principles. You should evaluate based on the role you are given.

Score each aspect from 0-1, starting at 0 and requiring justification for any increase:

1. Mathematical Foundation (0-1):
   0.00: Fundamentally flawed or missing
        Example: No equations, incorrect mathematical concepts
   0.25: Basic but problematic
        Example: Simple equations without proper variables defined
   0.50: Sound but incomplete
        Example: Correct equations but missing key relationships
   0.75: Strong with minor gaps
        Example: Well-formulated with some assumptions not fully justified
   1.00: Excellent and rigorous
        Example: Complete mathematical framework with all relationships justified

2. Real-World Integration (0-1):
   0.00: No connection to reality
        Example: Pure abstract model without practical context
   0.25: Superficial consideration
        Example: Mentioning real factors without incorporating them
   0.50: Partial integration
        Example: Some key factors included but others missing
   0.75: Good but not comprehensive
        Example: Most factors included but some interactions overlooked
   1.00: Complete integration
        Example: All relevant factors and interactions properly modeled

3. Technical Sophistication (0-1):
   0.00: Elementary/inappropriate
        Example: Using linear regression for clearly nonlinear problems
   0.25: Basic techniques only
        Example: Simple statistical methods without justification
   0.50: Appropriate but limited
        Example: Correct methods but not fully exploited
   0.75: Advanced with minor issues
        Example: Sophisticated methods with some gaps in implementation
   1.00: State-of-the-art
        Example: Cutting-edge techniques properly implemented

4. Validation Approach (0-1):
   0.00: No validation
        Example: Results presented without any verification
   0.25: Minimal testing
        Example: Basic sanity checks only
   0.50: Partial validation
        Example: Some test cases but not comprehensive
   0.75: Thorough but not complete
        Example: Multiple validation methods but missing edge cases
   1.00: Comprehensive validation
        Example: Multiple methods, edge cases, sensitivity analysis

5. Implementation Quality (0-1):
   0.00: Poor/incorrect
        Example: Errors in implementation, wrong formulas
   0.25: Basic but flawed
        Example: Correct concept but significant implementation errors
   0.50: Workable but needs improvement
        Example: Functions correctly but inefficient or unclear
   0.75: Good with minor issues
        Example: Well-implemented but some optimization possible
   1.00: Excellent implementation
        Example: Efficient, clear, and well-documented code

---

Your response must follow this exact format:

Your Response:
```json
{
    "mathematical_foundation": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "real_world_integration": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "technical_sophistication": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "validation": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "implementation": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "calculated_overall": 0.0,
    "overall_feedback": "Critical analysis of strengths and weaknesses"
}
```

---

Note: Scores must be exactly 0.00, 0.25, 0.50, 0.75, or 1.00. Start at 0 and justify each increment. Be extremely critical. You should also give your score and explaination from your role's perspective."""

     USER_PROMPT = """Please evaluate the modeling groundedness of the following mathematical modeling paper:

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
          
          if "implementation_quality" in result:
               result["implementation"] = result.pop("implementation_quality")
               
          # Calculate overall score as average of individual scores
          scores = [result[aspect]["score"] for aspect in [
               "mathematical_foundation", "real_world_integration", 
               "technical_sophistication", "validation", "implementation"
          ]]
          result["calculated_overall"] = sum(scores) / len(scores)
          result["role"] = role
          
          return result 