import sys
import os
import yaml
import json
import multiprocessing
from concurrent.futures import CancelledError
from concurrent.futures import ProcessPoolExecutor, as_completed
import traceback
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  
sys.path.append(BASE_DIR)

from src.ModelAgent.engines.core import Core
from src.ModelAgent.engines.writing import WritingEngine
from src.ModelAgent.engines.selection import SelectionEngine
from src.ModelAgent.engines.modeling import ModelingEngine
from src.ModelAgent.engines.data import DataAgent
from src.ModelAgent.engines.simulation import SimulationAgent
from src.ModelAgent.utils.shared_context import SharedContext


class BaseAgent:
    def __init__(self, config):
        self.config = config
        
        self.core = Core(config)
        self.shared_context = SharedContext(config)
        
        self.selection_engine = SelectionEngine(config, self.core, self.shared_context)
        self.modeling_engine = ModelingEngine(config, self.core, self.shared_context)
        self.data_agent = DataAgent(config, self.core, self.shared_context)
        self.simulation_agent = SimulationAgent(config, self.core, self.shared_context)
        self.writing_engine = WritingEngine(config, self.core, self.shared_context)
        
        self.exist = 0
        self.todo = 0
    
    def run(self):
        """
        Main execution entry with extra debug printing.
        """

        print(f"[INFO] BaseAgent for {self.config['gold_id']} started")

        # ---------- load previous context ----------
        if "context.json" in os.listdir(self.config["log_dir"]):
            self.shared_context.load_context(
                os.path.join(self.config["log_dir"], "context.json")
            )
            print("[INFO] Previous context loaded")

        # ---------- quick exit check ----------
        try:
            task_decomposition = self.shared_context.get_context(
                "selection_history"
            )[-1]["task_decomposition"]

            last_subtask_id = len(task_decomposition) - 1
            flag_key = f"factor_critics_{last_subtask_id}_0"

            if flag_key in self.shared_context.context:
                print("[INFO] All steps finished earlier – skipping")
                self.exist += 1
                return

        except (KeyError, IndexError):
            # no previous selection_history – fresh run
            pass

        # ---------- pipeline starts ----------
        print(f"[INFO] Working dir: {self.config['log_dir']}")
        self.todo += 1

        # idea
        self.shared_context.add_context("grading_points", self.config["requirements"])
        self.selection_engine.get_modeling_question()
        self.selection_engine.get_assumptions()
        self.selection_engine.selection_refine_loop()

        # modeling
        task_decomposition = self.shared_context.get_context("selection_history")[-1]["task_decomposition"]
        for subtask_idx in range(len(task_decomposition)):
            self.modeling_engine.modeling_refine_loop(subtask_idx, 0)
            self.modeling_engine.factor_extraction(subtask_idx, 0)
            self.modeling_engine.factor_critic(subtask_idx, 0)

        # data / modeling
        self.data_agent.run()
        self.simulation_agent.run()

        # writing
        for subtask_idx in range(len(task_decomposition)):
            try:
                self.writing_engine.write_data(subtask_idx, 0)
            except Exception as e:
                print(f"[WARN] write_data {subtask_idx} failed: {e}")
                traceback.print_exc()
            try:
                self.writing_engine.write_simulation(subtask_idx, 0)
            except Exception as e:
                print(f"[WARN] write_simulation {subtask_idx} failed: {e}")
                traceback.print_exc()

        self.writing_engine.get_restatement()
        self.writing_engine.write_solution()

        print(f"[INFO] BaseAgent for {self.config['gold_id']} finished")

def create_run_folder():
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_folder = f"../modelagent_runs/{timestamp}_run"
    os.makedirs(run_folder, exist_ok=True)
    print(f"Created run folder: {run_folder}")
    return run_folder


def process_problem(config, gold_id, problem_data):
    """
    One‐shot runner for a single MCM/ICM problem.

    Extra debugging:
    1. Print timestamp + worker pid at start.
    2. Catch any Exception, dump full traceback.
    3. If the exception has attributes such as status_code or error, dump them.
    """
    start_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{start_ts}] <pid={os.getpid()}> Start {gold_id}")

    # ---------- directory prep ----------
    base_path = config["base_path"]
    base_dir  = os.path.join(base_path, gold_id)

    os.makedirs(base_dir, exist_ok=True)
    log_dir   = os.path.join(base_dir, "log")
    work_dir = os.path.join(base_dir, "workspace")
    os.makedirs(log_dir,  exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)

    # ---------- build local config ----------
    problem_config = config.copy()
    problem_config.update(
        gold_id = gold_id,
        log_dir = log_dir,
        work_dir = work_dir,
        query   = problem_data["question"],
        grading_points = problem_data["decomposition"]["grading_points"],
    )

    exist = todo = 0

    try:
        agent = BaseAgent(problem_config)
        agent.run()
        exist = agent.exist
        todo  = agent.todo

    except Exception as e:
        # ---- rich debug info ----
        print(f"[ERROR] {gold_id} raised {type(e).__name__}: {repr(e)}")
        traceback.print_exc()

        # print extra fields if present (typical for OpenAI SDK errors)
        for attr in ("status_code", "code", "response", "message"):
            if hasattr(e, attr):
                print(f"  · {attr}: {getattr(e, attr)}")

    finally:
        end_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{end_ts}] <pid={os.getpid()}> End   {gold_id}")

    return gold_id, exist, todo

def main():
    with open("./model_config.yaml", "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    model_name = config["model"]["name"]
    base_path  = f"YOUR_ABSOLUTE_PATH_TO_WORKSPACE/{model_name}"
    os.makedirs(base_path, exist_ok=True)
    config["base_path"] = base_path

    with open("../data/modeling_data_final.json", "r") as f:
        data = json.load(f)
    
    max_workers = config.get("data", {}).get("max_workers", 4)
    num_workers = min(max_workers, len(data), multiprocessing.cpu_count())
    num_workers = 3

    print(f"Using {num_workers} workers")
    total_exist = total_todo = 0
    executor = ProcessPoolExecutor(max_workers=num_workers)

    try:
        future_to_id = {
            executor.submit(process_problem, config, gid, pdata): gid
            for gid, pdata in data.items()
        }

        for fut in as_completed(future_to_id):
            gid = future_to_id[fut]
            try:
                _, exist, todo = fut.result()
                total_exist += exist
                total_todo  += todo
                print(f"Completed {gid}")
            except CancelledError:
                print(f"Cancelled {gid}")
            except Exception as e:
                print(f"{gid} raised: {e}")

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt!  shutting down workers …")
        executor.shutdown(wait=False, cancel_futures=True)
        for p in multiprocessing.active_children():
            try:
                p.terminate()
            except OSError:
                pass
        raise
    else:
        executor.shutdown()

    print(f"Total exist: {total_exist}")
    print(f"Total todo : {total_todo}")


if __name__ == "__main__":
    multiprocessing.freeze_support() 
    main()