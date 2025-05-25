import os
import json
from copy import deepcopy

from src.ModelAgent.engines.core import Core
from src.ModelAgent.prompts.writing_restatement import RESTATEMENT_SYS, RESTATEMENT_USER
from src.ModelAgent.prompts.writing_simulation import SIMULATION_SYS, SIMULATION_USER
from src.ModelAgent.prompts.writing_data import DATA_SYS, DATA_USER
from src.ModelAgent.prompts.writing_solution import SOLUTION_SYS, SOLUTION_USER
from src.ModelAgent.utils.utils import form_message
from src.ModelAgent.utils.shared_context import SharedContext

class WritingEngine:
    def __init__(self, config, core, shared_context):
        self.config = config
        self.query = config["query"]
        self.core: Core = core
        self.shared_context: SharedContext = shared_context

    def parse_markdown_sections(self, content):
        """Parse markdown content to extract background and restatement sections"""
        # Extract content between ```markdown and ``` tags
        markdown_content = content.split("```markdown")[-1].split("```")[0].strip()
        
        # Split into sections
        sections = markdown_content.split("###")
        sections = [s.strip() for s in sections if s.strip()]
        
        background = ""
        restatement = ""
        
        for section in sections:
            if section.startswith("Background Analysis"):
                background = section.replace("Background Analysis", "").strip()
            elif section.startswith("Problem Restatement"):
                restatement = section.replace("Problem Restatement", "").strip()
        
        if not background and not restatement:
            background = markdown_content
            restatement = ""
        
        return background, restatement

    def get_restatement(self):
        """
        Get a comprehensive background analysis and restatement of the mathematical modeling problem.
        This is the first step in the modeling process.
        """
        if "problem_background" in self.shared_context.context and "problem_restatement" in self.shared_context.context:
            print("Already finish the restatement, skip!!")
            return
        
        print("Getting problem background and restatement")
        system = RESTATEMENT_SYS
        user = RESTATEMENT_USER.format(original_text=self.query)
        messages = form_message(system, user)
        response = self.core.execute(messages)
        
        # Parse the markdown response
        
        background, restatement = self.parse_markdown_sections(response)
        
        # Store both sections
        self.background = background
        self.restatement = restatement
        
        # Add to shared context
        self.shared_context.add_context("problem_background", background)
        self.shared_context.add_context("problem_restatement", restatement)
        
        print(">> Problem background:\n", background)
        print("\n>> Problem restatement:\n", restatement)
        
        return background, restatement

    
    def write_data(self, subtask_idx=0, approach_idx=0):
        if f"writing_data_{subtask_idx}_{approach_idx}" in self.shared_context.context:
            print("Already finish the data writing, skip!!")
            return
        
        modeling_history = self.shared_context.get_context(f"modeling_history_{subtask_idx}_{approach_idx}")[-1]
        modeling_objective = modeling_history["modeling_approach"]["objective"]
        modeling_approach = modeling_history["modeling_approach"]["modeling_approaches"]["approach"]
        modeling_application = modeling_history["modeling_approach"]["modeling_approaches"]["application"]
        modeling_implementation = modeling_history["modeling_implementation"]
        all_modeling_str = f"- Modeling Objective: {modeling_objective}\n\n- Modeling Approach: {modeling_approach}\n\n- Modeling Application: {modeling_application}"
        
        gold_id = self.config["gold_id"]
        model_name = self.config["model"]["name"]
        simulation_dir = f"../../output_workspace_modelagent/{model_name}/{gold_id}/workspace/simulation"
        if "modeling_default" in os.listdir(simulation_dir):
            simulation_dir = os.path.join(simulation_dir, "modeling_default")
        data_dir = os.path.join(simulation_dir, f"modeling_{subtask_idx}_{approach_idx}", "data")
        results_dir = os.path.join(simulation_dir, f"modeling_{subtask_idx}_{approach_idx}", "results")
        
        report_str = ""
        report_path = os.path.join(results_dir, "report.md")
        if os.path.exists(report_path):
            with open(report_path, "r") as f:
                report_str = f.read()
        if report_str == "":
            report_str = "No report file found in the directory."
        
        all_data_paths = []
        if "data_description.md" in os.listdir(data_dir) and "data.csv" in os.listdir(data_dir):
            all_data_paths.append((os.path.join(data_dir, "data_description.md"), os.path.join(data_dir, "data.csv")))
        for sub_dir in os.listdir(data_dir):
            if not os.path.isdir(os.path.join(data_dir, sub_dir)):
                continue
            sub_dir_path = os.path.join(data_dir, sub_dir)
            if "data_description.md" in os.listdir(sub_dir_path) and "data.csv" in os.listdir(sub_dir_path):
                all_data_paths.append((os.path.join(sub_dir_path, "data_description.md"), os.path.join(sub_dir_path, "data.csv")))
        
        all_data_history = []
        try:
            simulation_context = os.path.join(simulation_dir, f"modeling_{subtask_idx}_{approach_idx}", "context.json")
            with open(simulation_context, "r") as f:
                all_data_history = json.load(f)["data_collection_history"]
        except:
            pass
            
        all_data_str = ""
        for data_description_path, data_path in all_data_paths:
            try:
                with open(data_description_path, "r") as f:
                    data_description = f.read().replace("\n\n", "\n")
                with open(data_path, "r") as f:
                    data = f.read().strip()
                    if len(data.split("\n")) > 8:
                        data = "\n".join(data.split("\n")[:5]) + "\n...\n" + "\n".join(data.split("\n")[-3:]).strip()
                all_data_str += "- Data File Name: " + data_path.split("/")[-1] + "\n"
                all_data_str += f"- Data Description\n{data_description}\n\n- Data Content\n{data}\n\n\n"
            except:
                continue
        all_data_str = all_data_str.strip()
        if all_data_str == "":
            all_data_str = "No data files found in the directory."
    
        
        all_history_str = ""
        for data_history in all_data_history:
            try:
                summary = data_history["summary"]
                if len(summary.split("\n")) > 256:
                    summary = "\n".join(summary.split("\n")[:128]) + "\n...\n" + "\n".join(summary.split("\n")[-128:]).strip()
                thinking = data_history["details"]["call_data"]["thinking"]
                if len(thinking.split("\n")) > 256:
                    thinking = "\n".join(thinking.split("\n")[:128]) + "\n...\n" + "\n".join(thinking.split("\n")[-128:]).strip()
                all_history_str += f"- Thinking: {thinking}\n- Used Tool and Action: {summary}\n\n"
            except:
                continue
        all_history_str = all_history_str.strip()
        if all_history_str == "":
            all_history_str = "No data collection history found in the directory."
        
        system = DATA_SYS
        user = DATA_USER.format(
            modeling_implementation=modeling_implementation,
            all_modeling=all_modeling_str,
            all_data=all_data_str,
            all_history=all_history_str,
            report_file=report_str,
        )
        
        messages = form_message(system, user)
        response = self.core.execute(messages)
        # Parse the markdown response
        data = response.split("--- Markdown Begin ---")[-1].split("--- Markdown End ---")[0].strip()
        
        self.shared_context.add_context(f"writing_data_{subtask_idx}_{approach_idx}", data)
        print(">> Data writing:\n", response)
        return data
    
    def write_simulation(self, subtask_idx=0, approach_idx=0):
        if f"writing_simulation_{subtask_idx}_{approach_idx}" in self.shared_context.context:
            print("Already finish the simulation writing, skip!!")
            return
        
        modeling_history = self.shared_context.get_context(f"modeling_history_{subtask_idx}_{approach_idx}")[-1]
        modeling_objective = modeling_history["modeling_approach"]["objective"]
        modeling_approach = modeling_history["modeling_approach"]["modeling_approaches"]["approach"]
        modeling_application = modeling_history["modeling_approach"]["modeling_approaches"]["application"]
        modeling_implementation = modeling_history["modeling_implementation"]
        all_modeling_str = f"- Modeling Objective: {modeling_objective}\n\n- Modeling Approach: {modeling_approach}\n\n- Modeling Application: {modeling_application}"
        
        all_data_str = self.shared_context.get_context(f"writing_data_{subtask_idx}_{approach_idx}")
        
        gold_id = self.config["gold_id"]
        model_name = self.config["model"]["name"]
        simulation_dir = f"../../output_workspace_modelagent/{model_name}/{gold_id}/workspace/simulation"
        if "modeling_default" in os.listdir(simulation_dir):
            simulation_dir = os.path.join(simulation_dir, "modeling_default")
        
        results_dir = os.path.join(simulation_dir, f"modeling_{subtask_idx}_{approach_idx}", "results")
        report_str = ""
        report_path = os.path.join(results_dir, "report.md")
        if os.path.exists(report_path):
            with open(report_path, "r") as f:
                report_str = f.read()
        if report_str == "":
            report_str = "No report file found in the directory."

        all_simulation_history = []
        try:
            simulation_context = os.path.join(simulation_dir, f"modeling_{subtask_idx}_{approach_idx}", "context.json")
            with open(simulation_context, "r") as f:
                all_simulation_history = json.load(f)["data_collection_history"]
        except:
            pass
        
        all_history_str = ""
        for simulation_history in all_simulation_history:
            try:
                if simulation_history["is_critic"]:
                    continue
                summary = simulation_history["summary"]
                if len(summary.split("\n")) > 512:
                    summary = "\n".join(summary.split("\n")[:256]) + "\n...\n" + "\n".join(summary.split("\n")[-256:]).strip()
                thinking = simulation_history["details"]["call_data"]["thinking"]
                if len(thinking.split("\n")) > 256:
                    thinking = "\n".join(thinking.split("\n")[:128]) + "\n...\n" + "\n".join(thinking.split("\n")[-128:]).strip()
                all_history_str += f"- Thinking: {thinking}\n- Used Tool and Action: {summary}\n\n"
            except:
                continue
        all_history_str = all_history_str.strip()
        if all_history_str == "":
            all_history_str = "No modeling simulation history found in the directory."
            
            
        system = SIMULATION_SYS
        user = SIMULATION_USER.format(
            modeling_implementation=modeling_implementation,
            all_modeling=all_modeling_str,
            all_data=all_data_str,
            all_history=all_history_str,
            report_file=report_str,
        )
        
        messages = form_message(system, user)
        response = self.core.execute(messages)
        # Parse the markdown response
        simulation = response.split("--- Markdown Begin ---")[-1].split("--- Markdown End ---")[0].strip()
        self.shared_context.add_context(f"writing_simulation_{subtask_idx}_{approach_idx}", simulation)
        print(">> Simulation writing:\n", response)
        return simulation


    def write_solution(self):
        try:
            if f"writing_combined" in self.shared_context.context:
                print("Already finish the solution writing, skip!!")
                return
            
            grading_points = self.shared_context.get_context("grading_points")
            all_requirements = ""
            for idx, sub_point in enumerate(grading_points):
                all_requirements += f"## Modeling Requirement {idx+1}: {sub_point['category']}\n\n- Details: {sub_point['description']}\n\n"
            all_requirements = all_requirements.strip()
            
            task_decomposition = self.shared_context.get_context("selection_history")[-1]["task_decomposition"]
            
            writing = ""
            problem_background = self.shared_context.get_context("problem_background")
            problem_restatement = self.shared_context.get_context("problem_restatement")
            
            writing += f"# Problem Background\n{problem_background}\n\n\n# Problem Restatement\n{problem_restatement}\n\n\n"
        except:
            pass
        
        for subtask_idx in range(len(task_decomposition)):
            try:
                modeling_history = self.shared_context.get_context(f"modeling_history_{subtask_idx}_0")[-1]
                modeling_objective = modeling_history["modeling_approach"]["objective"]
                modeling_analysis = modeling_history["modeling_approach"]["analysis"]
                modeling_approach = modeling_history["modeling_approach"]["modeling_approaches"]["approach"]
                modeling_application = modeling_history["modeling_approach"]["modeling_approaches"]["application"]
                modeling_implementation = modeling_history["modeling_implementation"]
                all_modeling_str = f"## Modeling Analysis\n- Objective: {modeling_objective}\n\n- Analysis: {modeling_analysis}\n\n- Approach: {modeling_approach}\n\n- Application: {modeling_application}\n\n\n## Implementation: {modeling_implementation}"
                all_data_str = self.shared_context.get_context(f"writing_data_{subtask_idx}_0")
                all_data_str = f"## Data Collection\n{all_data_str}"
                all_simulation_str = self.shared_context.get_context(f"writing_simulation_{subtask_idx}_0")
                all_simulation_str = f"## Modeling Simulation\n{all_simulation_str}"
                writing += f"# Modeling Approach {subtask_idx+1}: {modeling_approach}\n\n{all_modeling_str}\n\n\n{all_data_str}\n\n\n{all_simulation_str}\n\n\n"
            except:
                pass
        
        writing = writing.strip()
        
        system = SOLUTION_SYS.format(
            all_requirements=all_requirements,
        )
        user = SOLUTION_USER.format(
            writing=writing,
        )
        
        messages = form_message(system, user)
        response = self.core.execute(messages)
        # Parse the markdown response
        solution = response.split("--- Markdown Begin ---")[-1].split("--- Markdown End ---")[0].strip()
        
        self.shared_context.add_context("writing_solution", solution)
        print(">> Solution writing:\n", response)
        
        writing_combined = f"{writing}\n\n\n# Solutions to All Modeling Requirements (Sub-tasks)\n{solution}"
        self.shared_context.add_context("writing_combined", writing_combined)
        
        return writing_combined
            
            
        
        
        
