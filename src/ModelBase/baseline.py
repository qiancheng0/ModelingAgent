import json
import os
import time
import yaml
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor

SYS_PROMPT = """You are an expert mathematical modeler tasked with creating comprehensive solutions to mathematical modeling problems. Your solutions must be of high quality and meet the following criteria:

1. Structural Completeness:
   - Clear problem restatement showing deep understanding
   - Well-justified assumptions with rationale
   - Detailed model implementation with mathematical rigor
   - Clear solution process and results presentation
   - Thorough analysis of results and limitations

2. Problem Requirements:
   - Address every requirement stated in the problem
   - Ensure each component of the solution aligns with problem objectives
   - Follow any specific format or deliverable requirements

3. Modeling Quality:
   - Use appropriate modeling approaches for the problem context
   - Consider real-world factors and constraints
   - Employ rigorous mathematical formalization
   - Clearly state and justify model parameters
   - Include validation methods

4. Data Handling:
   - Use authentic and reliable data sources
   - Justify data selection and preprocessing
   - Ensure sufficient data for meaningful analysis
   - Include data validation and quality checks

5. Analysis Depth:
   - Base conclusions on mathematical/experimental evidence
   - Provide insightful interpretation of results
   - Include sensitivity analysis where appropriate
   - Discuss limitations and uncertainties

6. Innovation:
   - Propose creative modeling approaches
   - Consider novel combinations of methods
   - Demonstrate potential real-world impact
   - Suggest practical implementation strategies

Your solution must follow this structure:

### Problem Restatement
[Clear restatement and interpretation of the problem]

### Assumptions and Justification
[List and justify key assumptions]

### Model Development
[Detailed mathematical model description]
- Variables and Parameters
- Equations and Relationships
- Constraints and Conditions

### Solution Process
[Step-by-step solution implementation]
- Data Collection and Processing
- Model Implementation
- Solution Methods

### Results and Analysis
[Comprehensive results presentation]
- Key Findings
- Sensitivity Analysis
- Validation
- Limitations

### Recommendations
[Practical implications and suggestions]

Note: Ensure mathematical rigor while maintaining clarity. Include equations, diagrams, and data analysis as needed."""

USER_PROMPT = """Please create a comprehensive mathematical modeling solution for the following problem:

{question}

Develop a complete solution following the specified structure."""

def form_messages(msg: str, system_prompt: str = "你好！"):
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': msg}
    ]
    return messages

def gpt_chatcompletion(messages, model="gpt-4o"):
    rounds = 0
    while True:
        rounds += 1
        try:
            if "gpt" in model or "gemini" in model:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0,
                    n=1,
                    max_tokens=8192,
                )
                content = response.choices[0].message.content
            else:
                messages.append({
                    "role": "user",
                    "content": "Please directly give me a long passage to address the modeling problem in markdown format."
                })
                response = client.chat.completions.create(
                    model=client.models.list().data[0].id,
                    messages=messages,
                    temperature=0,
                    n=1,
                    max_tokens=8192,
                )
                content = response.choices[0].message.content
            return content.strip()

        except Exception as e:
            print(f"Generation Error: {e}")
            time.sleep(20)
            if rounds > 3:
                raise Exception("Generation failed too many times")


def main(gold_id: str, data: dict, output_dir: str, answered_data: dict, log: dict, model: str = "gpt-4o"):
    if gold_id in answered_data and "error" not in answered_data[gold_id]:
        return
    
    print(f"Generating solution for {gold_id} ...")
    question = data["question"]
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate solution
    messages = form_messages(
        USER_PROMPT.format(question=question),
        SYS_PROMPT
    )
    
    output_file = os.path.join(output_dir, f"{gold_id}.json")
    
    try:
        solution = gpt_chatcompletion(messages, model=model)
        
        # Save the solution
        with open(output_file, 'w') as f:
            json.dump({
                "writing": solution,
                "metadata": {
                    "timestamp": time.time(),
                    "status": "success"
                }
            }, f, indent=4)
        
        # Update answered data
        answered_data[gold_id] = {
            "writing": solution,
            "metadata": {
                "timestamp": time.time(),
                "status": "success"
            }
        }
        
        log["success"] += 1
        print(f"!! Generated solution for {gold_id} !!")
        
    except Exception as e:
        print(f"Failed to generate solution for {gold_id}: {str(e)}")
        log["fail"] += 1
        answered_data[gold_id] = {
            "error": str(e),
            "metadata": {
                "timestamp": time.time(),
                "status": "failed"
            }
        }


if __name__ == '__main__':
    model = "gpt-4o" # Change to the model being tested
    config = yaml.safe_load(open("./model_config.yaml", "r"))
    
    if "gpt" in model:
        client = OpenAI(api_key=config["openai_api_key"])
    else:
        client = OpenAI(api_key="dummy", base_url="http://localhost:8000/v1")
    
    # Load problem data
    with open("../data/modeling_data_final.json") as f:
        all_data = json.load(f)
    
    # Setup output directory
    output_dir = f"../output_writings/ModelBase/{model}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Load or initialize answered data
    save_path = os.path.join(output_dir, "solutions_metadata.json")
    if os.path.exists(save_path):
        with open(save_path) as f:
            answered_data = json.load(f)
    else:
        answered_data = {}
    
    # Initialize log
    log = {"success": 0, "fail": 0}
    
    # Generate solutions in parallel
    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = [
            executor.submit(main, gold_id, data, output_dir, answered_data, log, model)
            for gold_id, data in all_data.items()
        ]
        for future in futures:
            future.result()
    
    # Save metadata
    with open(save_path, 'w') as f:
        json.dump(answered_data, f, indent=4)
    
    print(f"Completed - Success: {log['success']}, Failed: {log['fail']}") 