import json
from copy import deepcopy

from src.ModelAgent.engines.core import Core

from src.ModelAgent.prompts.modeling_critic import MODELING_CRITIC_SYS, MODELING_CRITIC_USER
from src.ModelAgent.prompts.modeling_generate import MODELING_GEN_SYS, MODELING_GEN_USER, MODELING_GEN_REFINE
from src.ModelAgent.prompts.factor_generation import MODELING_FACTOR_SYS, MODELING_FACTOR_USER
from src.ModelAgent.prompts.factor_critic import FACTOR_CRITIC_SYS, FACTOR_CRITIC_USER

from src.ModelAgent.utils.utils import form_message
from src.ModelAgent.utils.shared_context import SharedContext


class ModelingEngine:
    def __init__(self, config, core, shared_context):
        self.config = config
        self.core: Core = core
        self.shared_context: SharedContext = shared_context

    def modeling_refine_loop(self, subtask_idx=0, approach_idx=0):
        history = []
        
        modeling_question = self.shared_context.get_context("modeling_question")
        selection_history = self.shared_context.get_context("selection_history")
        proposed_model = selection_history[-1]
        modeling_approach = deepcopy(proposed_model["task_decomposition"][subtask_idx])
        # This step actually could be ran in multi-threading (different modeling approaches in parallel)
        modeling_approach["modeling_approaches"] = modeling_approach["modeling_approaches"][approach_idx]
        modeling_approach.pop("subtask")
        modeling_approach = json.dumps(modeling_approach, indent=2)
        
        system = MODELING_GEN_SYS
        user = MODELING_GEN_USER.format(modeling_question=modeling_question, modeling_approach=modeling_approach)
        
        round = 0
        while round < self.config["modeling"]["rounds"]:
            round += 1
            print(f"Model implementation round {round}...")
            
            messages = form_message(system, user)
            response = self.core.execute(messages)
            modeling_implementation = response.strip().strip("```markdown").strip("```").strip()
            print(">> Implemented model details:\n", modeling_implementation)
            
            # history.append(deepcopy(modeling_implementation))
            
            system = MODELING_CRITIC_SYS
            user = MODELING_CRITIC_USER.format(modeling_approach=modeling_approach, modeling_implementation=modeling_implementation)
            messages = form_message(system, user)
            response = self.core.execute(messages)
            critics = response.split("```json")[-1].split("```")[0].strip()
            print(">> Critics:\n", critics)
            try:
                critics = json.loads(critics)
            except:
                # TODO: fix json format based on the schema and model response, using GPT
                pass
            
            implemention_record = {
                "modeling_approach": json.loads(modeling_approach),
                "modeling_implementation": modeling_implementation,
                "user_feedback": critics
            }
                            
            # history.append(deepcopy(critics))
            history.append(deepcopy(implemention_record))
            
            modeling_implementation = "```markdown\n" + modeling_implementation + "\n```"
            critics = json.dumps(critics, indent=2)
            system = MODELING_GEN_SYS
            user = MODELING_GEN_REFINE.format(modeling_approach=modeling_approach, modeling_implementation=modeling_implementation, critics=critics)
        
        self.shared_context.add_context(f"modeling_history_{subtask_idx}_{approach_idx}", history)
        
        self.modeling_implementation = deepcopy(history[-1]["modeling_implementation"])
        self.modeling_approach = modeling_approach
    
    
    def factor_extraction(self, subtask_idx=0, approach_idx=0):
        print("Getting factor extracted from question")
        system = MODELING_FACTOR_SYS
        user = MODELING_FACTOR_USER.format(modeling_approach=self.modeling_approach, modeling_implementation="```markdown\n" + self.modeling_implementation.strip() + "\n```")
        messages = form_message(system, user)
        response = self.core.execute(messages)
        
        print(">> Factors:\n", response)
        try:
            self.explanation = response.strip().split("```json")[1].split("```")[1].strip()
            self.factors = response.strip().split("```json")[1].split("```")[0].strip()
            self.factors = json.loads(self.factors)
        except:
            # TODO: fix json format based on the schema and model response, using GPT
            pass
        
        self.shared_context.add_context(f"factors_{subtask_idx}_{approach_idx}", deepcopy(self.factors))
        self.shared_context.add_context(f"explanation_{subtask_idx}_{approach_idx}", deepcopy(self.explanation))
        

    def factor_critic(self, subtask_idx=0, approach_idx=0):
        print("Getting factor critic for the question ...")
        
        factors = self.shared_context.get_context(f"factors_{subtask_idx}_{approach_idx}")
        system = FACTOR_CRITIC_SYS
        user = FACTOR_CRITIC_USER.format(factors=factors)
        messages = form_message(system, user)
        response = self.core.execute(messages)
        
        print(">> Factor Critics:\n", response)
        try:
            self.factor_critics = response.strip().split("```json")[1].split("```")[0].strip()
            self.factor_critics = json.loads(self.factor_critics)
            print("Success in parsing!")
        except:
            # TODO: fix json format based on the schema and model response, using GPT
            pass
        
        self.shared_context.add_context(f"factor_critics_{subtask_idx}_{approach_idx}", deepcopy(self.factor_critics))
