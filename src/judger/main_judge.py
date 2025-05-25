import json
import os
import ast
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Set

from structural_coherency import StructuralCoherencyJudger
from scoring_decomposition import ScoringDecompositionJudger
from modeling_groundedness import ModelingGroundednessJudger
from data_groundedness import DataGroundednessJudger
from analysis_groundedness import AnalysisGroundednessJudger
from innovativeness import InnovativenessJudger

class MainJudger:
    def __init__(self):
        self.judgers = {
            "structural_coherency": StructuralCoherencyJudger(),
            "scoring_decomposition": ScoringDecompositionJudger(),
            "modeling_groundedness": ModelingGroundednessJudger(),
            "data_groundedness": DataGroundednessJudger(),
            "analysis_groundedness": AnalysisGroundednessJudger(),
            "innovativeness": InnovativenessJudger()
        }
        
        # Judgers that use role-based evaluation
        self.role_based_judgers = {
            "modeling_groundedness",
            "data_groundedness", 
            "analysis_groundedness",
            "innovativeness"
        }
        
    def run_judger(self, judger_name: str, writing: str, roles: list = None, grading_points: list = None) -> Dict[str, Any]:
        try:
            judger = self.judgers[judger_name]
            
            # Handle role-based judgers
            if judger_name in self.role_based_judgers and roles:
                results = []
                for role in roles:
                    result = judger.run(writing, role=role)
                    result["role"] = role
                    results.append(result)
                return {
                    "role_based_results": results,
                    "aggregated_score": sum(r.get("calculated_overall", 0) for r in results) / len(results)
                }
            
            # Handle non-role-based judgers
            if judger_name == "scoring_decomposition":
                return judger.run(writing, grading_points)
            return judger.run(writing)
            
        except Exception as e:
            print(f"Error in {judger_name}: {str(e)}")
            return {
                "error": str(e),
                "status": "failed",
                "judger": judger_name
            }
    
    def get_existing_results(self, output_dir: str, gold_id: str) -> Dict[str, Any]:
        """Read existing judgement results if they exist"""
        output_file = f"{output_dir}/{gold_id}.json"
        if os.path.exists(output_file):
            try:
                with open(output_file) as f:
                    results = json.load(f)
                return results.get("judgements", {})
            except:
                return {}
        return {}

    def get_missing_judgers(self, existing_results: Dict[str, Any]) -> Set[str]:
        """Determine which judgers need to be run"""
        missing = set(self.judgers.keys())
        for judger_name, result in existing_results.items():
            # Only consider result valid if it exists and has no error
            if result and "error" not in result:
                missing.remove(judger_name)
        return missing
    
    def judge(self, output_dir: str, gold_id: str, writing: str, grading_points: list, roles: list = None) -> Dict[str, Any]:
        # Initialize results structure
        results = {
            "gold_id": gold_id,
            "judgements": {},
            "metadata": {
                "success_count": 0,
                "failed_count": 0,
                "failed_judgers": [],
                "skipped_count": 0,
                "skipped_judgers": []
            }
        }
        
        # Get existing results
        existing_results = self.get_existing_results(output_dir, gold_id)
        missing_judgers = self.get_missing_judgers(existing_results)
        
        print(f"Missing judgers for {gold_id}: {missing_judgers}")
        
        # Add existing valid results to our results
        for judger_name, result in existing_results.items():
            if judger_name not in missing_judgers:
                results["judgements"][judger_name] = result
                results["metadata"]["skipped_count"] += 1
                results["metadata"]["skipped_judgers"].append(judger_name)
        
        if not missing_judgers:
            print(f"All judgements already exist for {gold_id}")
            return results
        
        # Run only missing judgers in parallel
        with ThreadPoolExecutor(max_workers=6) as executor:
            future_to_judger = {
                executor.submit(
                    self.run_judger, 
                    name, 
                    writing, 
                    roles if name in self.role_based_judgers else None,
                    grading_points if name == "scoring_decomposition" else None
                ): name
                for name in missing_judgers
            }
            
            for future in future_to_judger:
                name = future_to_judger[future]
                try:
                    result = future.result()
                    if "error" in result:
                        results["metadata"]["failed_count"] += 1
                        results["metadata"]["failed_judgers"].append(name)
                    else:
                        results["metadata"]["success_count"] += 1
                    results["judgements"][name] = result
                except Exception as e:
                    print(f"Error in {name}: {str(e)}")
                    results["judgements"][name] = {"error": str(e)}
                    results["metadata"]["failed_count"] += 1
                    results["metadata"]["failed_judgers"].append(name)
        
        with open(f"{output_dir}/{gold_id}.json", 'w') as f:
            json.dump(results, f, indent=4)
        
        return results

def process_gold_id(args):
    gold_id, data, output_dir, judger = args
    if "writing" not in data:  # Skip if no writing to evaluate
        return
    
    writing = data["writing"]
    criteria = data["criteria"]
    grading_points = criteria.get("decomposition", {}).get("grading_points", [])
    roles = criteria.get("eval_roles", [])
    
    print(f"Evaluating {gold_id}...")
    results = judger.judge(output_dir, gold_id, writing, grading_points, roles)
    print(f"Completed {gold_id} - Success: {results['metadata']['success_count']}, "
          f"Failed: {results['metadata']['failed_count']}, "
          f"Skipped: {results['metadata']['skipped_count']}")
    return gold_id, results

def main():
    for model, level in zip(["Qwen2.5-72B-Instruct"], ["ModelAgent"]):
        try:
            # Load problem data
            with open("../../data/modeling_data_final.json") as f:
                criterias = json.load(f)
            with open(f"../../output_writings/{level}/{model}/solutions_metadata.json") as f:
                writings = json.load(f)
            
            output_dir = f"../../output_judge/{level}/{model}"
            os.makedirs(output_dir, exist_ok=True)
            all_data = {}
            for gold_id, criteria in criterias.items():
                    all_data[gold_id] = {
                        "criteria": criteria,
                    }
            for gold_id, writing in writings.items():
                    if "writing" not in writing:
                        continue
                    all_data[gold_id]["writing"] = writing
            
            print(len(all_data))
            
            judger = MainJudger()
            
            # Process problems in parallel
            with ThreadPoolExecutor(max_workers=10) as executor:
                args = [(gold_id, data, output_dir, judger) for gold_id, data in all_data.items()]
                results = list(executor.map(process_gold_id, args))
        except:
            continue

if __name__ == "__main__":
    main()