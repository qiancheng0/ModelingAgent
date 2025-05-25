import json
import ast
import os
from openai import OpenAI

class DataGroundednessJudger:
    SYS_PROMPT = """You are currently evaluating mathematical modeling papers. Your task is to assess how well the solution is grounded in data and evidence. You should evaluate based on the role you are given.

Score each aspect from 0-1, starting at 0 and requiring justification for any increase:

1. Data Quality (0-1):
   0.00: No data or invalid data
        Example: Made-up numbers without sources
   0.25: Poor quality/unreliable
        Example: Single unreliable source, outdated data
   0.50: Acceptable but limited
        Example: Reliable source but incomplete dataset
   0.75: Good with minor issues
        Example: Multiple reliable sources, small gaps
   1.00: Excellent data quality
        Example: Multiple verified sources, comprehensive coverage

2. Data Processing (0-1):
   0.00: No processing/invalid
        Example: Raw data used without cleaning
   0.25: Basic processing only
        Example: Simple averaging without outlier removal
   0.50: Standard processing
        Example: Basic cleaning and normalization
   0.75: Advanced processing
        Example: Sophisticated cleaning with justification
   1.00: Comprehensive processing
        Example: Full pipeline with validation at each step

3. Statistical Analysis (0-1):
   0.00: No analysis/incorrect
        Example: No statistical methods used
   0.25: Basic statistics only
        Example: Mean/median without confidence intervals
   0.50: Standard analysis
        Example: Basic hypothesis testing
   0.75: Advanced analysis
        Example: Multiple statistical methods with validation
   1.00: Rigorous analysis
        Example: Comprehensive statistical framework with robustness checks

4. Data Integration (0-1):
   0.00: No integration
        Example: Data disconnected from model
   0.25: Poor integration
        Example: Forced fit without justification
   0.50: Partial integration
        Example: Some aspects well-integrated, others not
   0.75: Good integration
        Example: Most data well-integrated with clear reasoning
   1.00: Perfect integration
        Example: All data seamlessly integrated with full justification

5. Validation & Testing (0-1):
   0.00: No validation
        Example: Results accepted without testing
   0.25: Minimal testing
        Example: Basic sanity checks only
   0.50: Standard validation
        Example: Cross-validation without sensitivity analysis
   0.75: Thorough validation
        Example: Multiple validation methods
   1.00: Comprehensive validation
        Example: Full validation suite with sensitivity analysis

---

Your response must follow this exact format:

Your Response:
```json
{
    "data_quality": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "data_processing": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "statistical_analysis": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "data_integration": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "validation": {
        "score": 0.0,
        "explanation": "Detailed justification for score"
    },
    "calculated_overall": 0.0,
    "overall_feedback": "Critical analysis of strengths and weaknesses"
}
```

---

Note: Scores must be exactly 0.00, 0.25, 0.50, 0.75, or 1.00. Start at 0 and justify each increment. Be extremely critical. You should also give your score and explaination from your role's perspective."""

    USER_PROMPT = """Please evaluate the data groundedness of the following mathematical modeling paper:

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
        
        # Calculate overall score as average of individual scores
        scores = [result[aspect]["score"] for aspect in [
            "data_quality", "data_processing", "statistical_analysis",
            "data_integration", "validation"
        ]]
        result["calculated_overall"] = sum(scores) / len(scores)
        result["role"] = role
        
        return result 