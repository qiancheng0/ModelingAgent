import json
from copy import deepcopy

from src.ModelAgent.engines.core import Core

from src.ModelAgent.prompts.assumption import ASSUMPPTION_SYS, ASSUMPPTION_USER
from src.ModelAgent.prompts.question_extract import EXTRACT_MODELING_SYS, EXTRACT_MODELING_USER
from src.ModelAgent.prompts.selection_critic import SELECT_CRITIC_SYS, SELECT_CRITIC_USER
from src.ModelAgent.prompts.selection_generate import SELECT_GEN_SYS, SELECT_GEN_USER, SELECT_GEN_REFINE

from src.ModelAgent.utils.utils import form_message
from src.ModelAgent.utils.shared_context import SharedContext

class SelectionEngine:
    def __init__(self, config, core, shared_context):
        self.config = config
        self.query = config["query"]
        self.core: Core = core
        self.shared_context: SharedContext = shared_context

    def get_modeling_question(self):
        print("Getting modeling question")
        system = EXTRACT_MODELING_SYS
        user = EXTRACT_MODELING_USER.format(original_text=self.query)
        messages = form_message(system, user)
        response = self.core.execute(messages)
        self.modeling_question = response.strip()
        print(">> Modeling question:\n", self.modeling_question)
        self.shared_context.add_context("modeling_question", self.modeling_question)
        
    
    def get_assumptions(self):
        print("Getting assumptions")
        system = ASSUMPPTION_SYS
        user = ASSUMPPTION_USER.format(modeling_question=self.modeling_question)
        messages = form_message(system, user)
        response = self.core.execute(messages)
        self.assumptions = response.strip().strip("```json").strip("```").strip()
        print(">> Assumptions:\n", self.assumptions)
        try:
            self.assumptions = json.loads(self.assumptions)
        except:
            # TODO: fix json format based on the schema and model response, using GPT
            pass
        self.shared_context.add_context("assumptions", self.assumptions)
    
    
    def selection_refine_loop(self):
        history = []
        
        system = SELECT_GEN_SYS
        user = SELECT_GEN_USER.format(modeling_question=self.modeling_question)
        
        round = 0
        while round < self.config["selection"]["rounds"]:
            round += 1
            print(f"Model proposing round {round}...")
            
            messages = form_message(system, user)
            response = self.core.execute(messages)
            proposed_model = response.split("```json")[-1].split("```")[0].strip()
            print(">> Proposed model:\n", proposed_model)
            try:
                proposed_model = json.loads(proposed_model)
            except:
                # TODO: fix json format based on the schema and model response, using GPT
                pass
            
            # history.append(deepcopy(proposed_model))
            subtasks = proposed_model["task_decomposition"]
            
            all_critics = []
            for subtask in subtasks:
                system = SELECT_CRITIC_SYS
                user = SELECT_CRITIC_USER.format(subtask=subtask)
                messages = form_message(system, user)
                response = self.core.execute(messages)
                # from IPython import embed; embed()
                critics = response.split("```json")[-1].split("```")[0].strip()
                print(">> Critics:\n", critics)
                try:
                    critics = json.loads(critics)
                except:
                    # TODO: fix json format based on the schema and model response, using GPT
                    pass
                
                all_critics.extend(deepcopy(critics))
                
                for critic in critics:
                    approach = critic.pop("approach")
                    for modeling_approach in subtask["modeling_approaches"]:
                        if modeling_approach["approach"] == approach:
                            # the variable propose_model is updated in place, now with user feedback
                            modeling_approach["user_feedback"] = critic
                            break
                            
            # history.append(deepcopy(all_critics))
            history.append(deepcopy(proposed_model))
            
            system = SELECT_GEN_SYS
            user = SELECT_GEN_REFINE.format(modeling_question=self.modeling_question, proposed_model=proposed_model)
        
        self.shared_context.add_context("selection_history", history)
        self.proposed_model = proposed_model
        # May further add some selection / ranking techniques to select the best model
        self.rank_proposed_model()
        # Later may only adopt the top-k models for trial
        
        
    def rank_proposed_model(self):
        # In-place sorting of the modeling_approaches based on the user_feedback["overall_score"]
        for subtask in self.proposed_model["task_decomposition"]:
            # sort the modeling_approach based on the modeling_approach["user_feedback"]["overall_score"]
            subtask["modeling_approaches"] = sorted(subtask["modeling_approaches"], key=lambda x: x["user_feedback"]["overall_score"], reverse=True)
        
        
        
        
            
        
            
        
