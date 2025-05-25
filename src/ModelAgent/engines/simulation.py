import os
import json
import time
import datetime
import shutil
import traceback
from typing import Any

from src.ModelAgent.engines.core import Core
from src.ModelAgent.utils.shared_context import SharedContext
from src.ModelAgent.utils.tool_handler import ToolHandler
from src.ModelAgent.prompts.simulation_critic import (
            MODELING_CRITIC_SYS, MODELING_CRITIC_USER, MODELING_CRITIQUE_FUNCTION_SCHEMA
        )

class SimulationAgent:
    """
    Agent focused on mathematical modeling, simulation and perturbation experiments
    Uses LLM to develop models, run simulations, and analyze results
    Based on data acquired from DataAgent
    """
    # Color definitions
    COLOR = {
        "system":"\033[32m","user":"\033[34m","agent":"\033[35m",
        "tool":"\033[33m","critic":"\033[36m",
        "warn":"\033[33m","error":"\033[31m","info":"\033[0m",
    }
    
    def __init__(
        self,
        config: dict,                    # Configuration with work_dir / log_dir / tool & model settings
        core: Core,                      # LLM scheduling core
        shared_context: SharedContext,   # Shared state across agents
    ):
        """
        Initialize SimulationAgent with multi-directory workspace structure:
        - Creates clean simulation workspace at work_dir/simulation
        - Identifies all modeling groups from context.json
        - Creates isolated modeling directories for each group
        - Copies data directly to each group directory
        - Sets up tool handler for file operations

        Args:
            config: Contains model, tool settings, work_dir and log_dir paths
            core: Core implementation for LLM calls
            shared_context: For sharing information between agents
        """
        # 0. Input validation
        if "work_dir" not in config or "log_dir" not in config:
            raise ValueError("config must contain work_dir and log_dir")
        
        # 1. Save basic properties
        self.config = config
        self.core = core
        self.shared_context = shared_context
        
        # Get simulation config (if exists), otherwise use defaults
        simulation_config = config.get("simulation", {})
        self.max_api_retries = simulation_config.get("max_api_retries", 5)
        self.api_base_wait_time = simulation_config.get("api_base_wait_time", 10)
        # Add auto_early_stop config parameter, default True
        self.auto_early_stop = simulation_config.get("auto_early_stop", True)
        # Add overwrite config parameter, default True
        self.overwrite = simulation_config.get("overwrite", True)
        
        # 2. Define path constants (with absolute paths)
        self.work_dir = os.path.abspath(config["work_dir"])
        self.log_dir = os.path.abspath(config["log_dir"])
        self.sim_root = os.path.join(self.work_dir, "simulation")
        self.workspace_path = self.sim_root
        
        # Initialize history_file path (early placement to ensure _log_print is available)
        self.history_file = os.path.join(self.sim_root, "history.txt")
        
        # Add set to prevent duplicate TXT log records
        self.recorded_critic_logs = set()
        
        # 3. Handle simulation directory (clear based on overwrite setting)
        if self.overwrite and os.path.exists(self.sim_root):
            self._log_print("warn", f"Clearing simulation directory: {self.sim_root} (overwrite=True)")
            shutil.rmtree(self.sim_root)
            os.makedirs(self.sim_root)
        elif not os.path.exists(self.sim_root):
            self._log_print("info", f"Creating simulation directory: {self.sim_root}")
            os.makedirs(self.sim_root)
        else:
            self._log_print("info", f"Using existing simulation directory: {self.sim_root} (overwrite=False)")
        
        # 4. Load context.json
        ctx_path = os.path.join(self.log_dir, "context.json")
        try:
            with open(ctx_path, "r", encoding="utf-8") as f:
                self.context_dict = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Context file not found at {ctx_path}")
        
        # 5. Ensure grading_points are available, use defaults if not found
        if "grading_points" not in self.context_dict or not self.context_dict["grading_points"]:
            self._log_print("warn", "No grading_points found in context.json, using default scoring points")
            self.context_dict["grading_points"] = [
                {"category": "Problem Understanding", "description": "Understanding of the problem and its requirements"},
                {"category": "Mathematical Model", "description": "Quality and appropriateness of the mathematical model"},
                {"category": "Solution Method", "description": "Effectiveness of the solution approach"},
                {"category": "Results Analysis", "description": "Analysis and interpretation of results"},
                {"category": "Conclusion", "description": "Quality of conclusions and recommendations"}
            ]
        else:
            self._log_print("info", f"Read {len(self.context_dict['grading_points'])} scoring points from context.json")
        
        # 6. Backup initial values of all modeling_history related keys
        self.initial_modeling_histories = {}
        for key, value in self.context_dict.items():
            if key.startswith("modeling_history"):
                self.initial_modeling_histories[key] = value.copy() if isinstance(value, list) else value
        
        # 7. Parse modeling groups
        self._parse_groups()
        
        # 8. Create and write to history.txt (must come BEFORE data copy)
        self._initialize_history_file()
        
        # 9. Create group directories and copy data directly to each
        self._create_group_dirs_and_copy_data()
        
        # 10. Initialize ToolHandler (but don't set environment variables, will be set when running each task)
        self.tool_handler = ToolHandler(config)
        self.tool_map = self.tool_handler.tool_map
        
        # 11. Share group paths and task_table in context_dict
        self.context_dict["simulation_group_paths"] = self.group_paths
        self.context_dict["task_table"] = self.task_table
        
        # Log initialization completed
        self._log_print("system", "Init completed")
    
    def _log_print(self, level:str, text:str, truncate:int=1_000):
        """Terminal color + history.txt without truncation"""
        color = self.COLOR.get(level, "\033[0m")
        reset = "\033[0m"
        tag = level.upper()

        show = text if len(text) <= truncate else text[:truncate] + "...(truncated)"
        print(f"{color}[{tag}] {show}{reset}")

        try:
            # Ensure history_file directory exists
            if not hasattr(self, "history_file") or not self.history_file:
                if hasattr(self, "sim_root"):
                    self.history_file = os.path.join(self.sim_root, "history.txt")
                else:
                    # Create emergency log file
                    self.history_file = "simulation_emergency.log"
            
            ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] [{tag}] {text}\n")
        except Exception as e:
            print(f"\033[31m[ERROR] write log failed: {e}\033[0m")
    
    def _optimize_messages_for_length(self, messages:list[dict], max_length:int = 200_000) -> list[dict]:
        """
        Keep all system messages; last ≤10 user messages; all assistant messages;
        Ensure each assistant with tool_calls has corresponding function or tool response
        """
        if not messages: 
            return messages

        cur_len = sum(len(m.get("content","")) for m in messages if m.get("content"))
        if cur_len <= max_length: 
            return messages     # No need to trim

        # 1) System messages
        sys_msgs = [m for m in messages if m["role"]=="system"]

        # 2) Last 10 user messages
        user_msgs = [m for m in messages if m["role"]=="user"][-10:]

        # 3) Assistant messages and their corresponding function or tool responses
        cleaned_msgs = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            
            # Handle assistant messages and their subsequent responses
            if msg["role"] == "assistant":
                # Check for tool_calls
                has_tool_calls = False
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    has_tool_calls = True
                elif isinstance(msg, dict) and msg.get("tool_calls"):
                    has_tool_calls = True
                
                if has_tool_calls:
                    # Save this assistant message
                    assistant_msg = msg
                    paired_responses = []
                    
                    # Collect all function or tool messages that follow
                    j = i + 1
                    while j < len(messages) and (messages[j]["role"] == "function" or messages[j]["role"] == "tool"):
                        paired_responses.append(messages[j])
                        j += 1
                    
                    # Only keep this assistant message if there is at least one response
                    if len(paired_responses) > 0:
                        cleaned_msgs.append(assistant_msg)
                        cleaned_msgs.extend(paired_responses)
                    
                    # Jump to after the last processed message
                    i = j
                else:
                    # Regular assistant message, add directly
                    cleaned_msgs.append(msg)
                    i += 1
            elif msg["role"] == "system" or msg["role"] == "user":
                # System and user messages already handled separately, skip
                i += 1
            else:
                # Skip standalone function/tool messages (no preceding assistant)
                i += 1
        
        # Combine all messages
        result = sys_msgs + user_msgs + cleaned_msgs
        
        # Final tool_call pairing check
        # Ensure each assistant with tool_calls has paired tool messages
        final_result = []
        i = 0
        while i < len(result):
            msg = result[i]
            
            if msg["role"] == "assistant" and (msg.get("tool_calls") or (hasattr(msg, "tool_calls") and msg.tool_calls)):
                # Get set of tool call IDs
                tool_call_ids = set()
                tool_calls = msg.get("tool_calls") or getattr(msg, "tool_calls", [])
                
                for tc in tool_calls:
                    if isinstance(tc, dict) and tc.get("id"):
                        tool_call_ids.add(tc.get("id"))
                    elif hasattr(tc, "id"):
                        tool_call_ids.add(tc.id)
                
                # Only perform pairing check if there are tool call IDs
                if tool_call_ids:
                    final_result.append(msg)
                    
                    # Find subsequent paired tool responses
                    paired_ids = set()
                    j = i + 1
                    while j < len(result) and (result[j]["role"] == "function" or result[j]["role"] == "tool"):
                        response = result[j]
                        if response["role"] == "tool" and response.get("tool_call_id") in tool_call_ids:
                            paired_ids.add(response.get("tool_call_id"))
                            final_result.append(response)
                        elif response["role"] == "function" and response.get("name") in [tc.function.name if hasattr(tc, "function") else tc.get("function", {}).get("name") for tc in tool_calls]:
                            # Compatible with old-style function responses
                            final_result.append(response)
                        j += 1
                    
                    # If no paired responses found, add an empty tool response to avoid 400 error
                    if not paired_ids and tool_call_ids:
                        self._log_print("warn", f"No paired response found, adding placeholder tool response to avoid 400 error")
                        for tc_id in tool_call_ids:
                            final_result.append({
                                "role": "tool",
                                "tool_call_id": tc_id,
                                "name": "placeholder",
                                "content": json.dumps({"error": "Missing response placeholder"})
                            })
                    
                    i = j
                else:
                    # Regular assistant message
                    final_result.append(msg)
                    i += 1
            else:
                # Other message types add directly
                final_result.append(msg)
                i += 1
        
        return final_result
    
    def _all_tool_calls_paired(self, messages):
        """
        Check if all tool_calls in assistant messages have corresponding tool responses
        
        Args:
            messages: Message list
            
        Returns:
            bool: True if all tool_calls have corresponding tool responses
        """
        open_ids = set()
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg.get("tool_calls"):
                    if isinstance(tc, dict) and tc.get("id"):
                        open_ids.add(tc.get("id"))
                    elif hasattr(tc, "id"):
                        open_ids.add(tc.id)
            elif msg.get("role") == "tool" and msg.get("tool_call_id"):
                open_ids.discard(msg.get("tool_call_id"))
        
        if open_ids:
            self._log_print("warn", f"Unpaired tool_call_ids: {open_ids}")
            return False
        return True
    
    def _call_llm_with_tools(
            self,
            messages: list[dict],
            tools_schema: list[dict],
            *,
            model: str | None = None,
    ) -> 'Any':  # Return type depends on actual model API used
        """
        Unified LLM tool call entry:
          • Select appropriate model API based on model.type in config
          • Automatically trim messages
          • Automatic retry + exponential backoff
          • Automatic debug printing & logging
        """
        max_retry = self.max_api_retries
        wait_base = self.api_base_wait_time
        retry_count = 0
        model_type = self.config.get("model", {}).get("type", "openai")
        
        # Check model type
        if model_type != "openai":
            self._log_print("warn", f"Model type {model_type} may not fully support tool calls, attempting execution")
        
        while True:
            trimmed = self._optimize_messages_for_length(messages)
            # —— Debug output before sending
            last_user = next((m["content"] for m in reversed(trimmed) if m["role"]=="user"), "")
            self._log_print("tool", f"Prompt preview: {last_user[:150]}...")
            
            # Check tool_call_id pairing completeness
            if not self._all_tool_calls_paired(trimmed):
                self._log_print("error", "Found unpaired tool_call_ids, attempting repair")
                # Try to repair - remove last assistant message with tool_calls
                for i in range(len(trimmed) - 1, -1, -1):
                    if trimmed[i].get("role") == "assistant" and trimmed[i].get("tool_calls"):
                        del trimmed[i]
                        self._log_print("warn", f"Removed unpaired assistant message at index {i}")
                        break
                
                # Check again
                if not self._all_tool_calls_paired(trimmed):
                    self._log_print("error", "Repair failed, still have unpaired tool_call_ids")
                    raise RuntimeError("Unpaired tool_call_ids in messages, cannot continue")

            try:
                t0 = time.time()
                
                # OpenAI model handling
                if model_type == "openai":
                    resp = self.core.function_call_execute(
                        messages=trimmed,
                        functions=tools_schema,
                    )

                else:
                    # Default to using function_call_execute
                    self._log_print("warn", f"Using default method to call {model_type} model")
                    resp = self.core.function_call_execute(
                        messages=trimmed,
                        functions=tools_schema,
                    )
                    
                self._log_print(
                    "tool",
                    f"LLM call success in {time.time()-t0:.2f}s, model={model_type}"
                )

                # ——— Print tool_calls / assistant summary
                if hasattr(resp, "choices") and resp.choices:
                    msg = resp.choices[0].message
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        summary = {}
                        for tc in msg.tool_calls:
                            try:
                                args = json.loads(tc.function.arguments)
                                clean = {k:v for k,v in args.items() if k not in ("thinking","finish")}
                                summary[tc.function.name] = clean
                            except Exception:
                                summary[tc.function.name] = "parse-error"
                        self._log_print("tool", f"tool_calls: {json.dumps(summary, ensure_ascii=False)}")
                    elif hasattr(msg, "content") and msg.content:
                        self._log_print("agent", f"assistant: {msg.content[:150]}...")
                else:
                    self._log_print("tool", f"Unusual response format: {str(resp)[:150]}...")

                return resp                                             # ← Exit on success

            except Exception as e:
                retry_count += 1
                is_rate = "429" in str(e)
                if retry_count > max_retry:
                    self._log_print("error", f"LLM call failed {max_retry} times → abort. Last error: {e}")
                    raise
                wait = wait_base * (2 ** (retry_count - 1))
                if is_rate:   # Force longer wait for 429
                    wait = max(wait, 30)
                self._log_print("warn", f"LLM error ({e}); retry {retry_count}/{max_retry} after {wait}s")
                time.sleep(wait)
    
    def _parse_groups(self):
        """Parse modeling groups from context_dict"""
        self.task_table = {}
        
        # Look for keys with 'factors_' prefix
        for key in self.context_dict.keys():
            if key.startswith("factors_"):
                suffix = key.replace("factors_", "")
                hist_key = f"modeling_history_{suffix}"
                self.task_table[suffix] = {
                    "factors_key": key,
                    "history_key": hist_key if hist_key in self.context_dict else None
                }
        
        # If no suffixed keys found, use default
        if not self.task_table:
            self.task_table["default"] = {
                "factors_key": "factors",
                "history_key": "modeling_history" if "modeling_history" in self.context_dict else None
            }
        
        self._log_print("info", f"Found {len(self.task_table)} modeling groups: {', '.join(self.task_table.keys())}")
    
    def _get_data_sources(self):
        """
        Get all original data source directories/file paths for multiple copying
        
        Returns:
            list: List of data source paths
        """
        src_dirs = []
        
        # Check data_folder_path in context_dict
        if "data_folder_path" in self.context_dict and self.context_dict["data_folder_path"]:
            data_path = self.context_dict["data_folder_path"]
            if os.path.exists(data_path):
                src_dirs.append(data_path)
        
        # Check file paths in data_collection_results
        if "data_collection_results" in self.context_dict:
            results = self.context_dict["data_collection_results"]
            
            # Handle different result formats
            iterator = []
            if isinstance(results, dict):
                iterator = results.values()
            elif isinstance(results, list):
                iterator = results
            
            for item in iterator:
                if not isinstance(item, dict):
                    continue
                    
                # Look for file paths
                for key in ["csv_file", "md_file"]:
                    if key in item and item[key]:
                        file_path = item[key]
                        if os.path.exists(file_path):
                            parent_dir = os.path.dirname(file_path)
                            if parent_dir not in src_dirs:
                                src_dirs.append(parent_dir)
        
        return src_dirs
    
    def _create_group_dirs_and_copy_data(self):
        """Create modeling directories for each group and copy data directly to each"""
        self.group_paths = {}

        try:
            # 1) Collect all original data sources (directories or files)
            src_dirs = self._get_data_sources()

            # 2) Create directories & copy data for each modeling group
            for suffix in self.task_table.keys():
                grp_root = os.path.join(self.sim_root, f"modeling_{suffix}")

                # Create subdirectories
                subdirs = ["data", "model", "experiments", "results"]
                paths = {"root": grp_root}
                for name in subdirs:
                    dir_path = os.path.join(grp_root, name)
                    os.makedirs(dir_path, exist_ok=True)
                    paths[name] = dir_path

                # === Copy data sources to <group>/data ===
                copied_dirs  = 0
                copied_files = 0

                def _safe_copy(src_path: str, dst_root: str):
                    nonlocal copied_dirs, copied_files
                    try:
                        if os.path.isdir(src_path):
                            # Target: <group>/data/<original directory name>
                            dst_path = os.path.join(dst_root, os.path.basename(src_path))
                            shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                            copied_dirs += 1
                        else:  # File
                            shutil.copy2(src_path, dst_root)
                            copied_files += 1
                    except OSError as e:
                        if "No space left on device" in str(e):
                            raise RuntimeError(f"Insufficient disk space when copying {src_path}")
                        self._log_print("warn", f"Failed to copy {src_path}: {e}")

                for src in src_dirs:
                    _safe_copy(src, paths["data"])

                # Record paths
                self.group_paths[suffix] = paths
                self._log_print("info",
                    f"Group {suffix}: Copied {copied_dirs} dirs, {copied_files} files to {paths['data']}")

        except Exception as e:
            self._log_print("error", f"Unexpected error copying data: {e}")
            traceback.print_exc()
            raise
    
    def _initialize_history_file(self):
        """Initialize history.txt with header and initial information"""
        try:
            timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(self.history_file, "w", encoding="utf-8") as f:
                f.write(f"=== SimulationAgent History (UTC+0) ===\n")
                f.write(f"[{timestamp}] Init started\n")
                f.write(f" ├─ workspace_path : {self.workspace_path}\n")
                f.write(f" ├─ groups         : {' , '.join(self.task_table.keys())}\n")
                
                # List each group's path intent
                for i, suffix in enumerate(self.task_table.keys()):
                    prefix = " │   ├─" if i < len(self.task_table) - 1 else " │   └─"
                    f.write(f"{prefix} {suffix.ljust(8)} -> modeling_{suffix}\n")
                
                # Data copy statistics will be added by _create_group_dirs_and_copy_data
        except Exception as e:
            self._log_print("error", f"Failed to write to history file: {str(e)}")
            # Try to create a different log file if possible
            try:
                fallback_log = os.path.join(self.sim_root, "simulation_error.log")
                with open(fallback_log, "w", encoding="utf-8") as f:
                    f.write(f"Error initializing history file: {str(e)}\n")
            except:
                pass  # If even this fails, just continue without logging
    
    # ===== New helper functions supporting single_modeling_run =====
    
    def _utc(self) -> str:
        """Return UTC timestamp string in format: YYYY-MM-DD HH:MM:SS"""
        return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    def _load_json(self, path) -> dict:
        """Load JSON file, return empty dict if not found or error"""
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self._log_print("error", f"Failed to load JSON from {path}: {e}")
            return {}
    
    def _save_json(self, path, obj):
        """Save object to JSON file"""
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self._log_print("error", f"Failed to save JSON to {path}: {e}")
            return False
    
    def _append_sim_history_entry(self, iter_idx:int, call_dict:dict, tool_out:dict, critic:bool=False):
        """Add iteration information to simulation_history (JSON format)"""
        try:
            # Load current context
            ctx = self._load_json(self.sim_context_path)
            
            # Ensure simulation_history key exists
            if "simulation_history" not in ctx:
                ctx["simulation_history"] = []
            
            # ---------- Deduplication: Don't write duplicates of same type in same iteration ----------
            # Critic records: Strict deduplication by iter_idx and critic flag
            if critic:
                for old in ctx["simulation_history"]:
                    if old["iteration"] == iter_idx and old.get("is_critic", False) == critic:
                        # Already have critic record for this iteration → return directly, avoid duplicate write
                        self._log_print("info", f"Skipping duplicate record: critic iteration {iter_idx}")
                        return True
            # Non-critic records: Control number of tool call records per iteration
            else:
                # Count non-critic records for current iteration
                iter_records = [e for e in ctx["simulation_history"] 
                              if e["iteration"] == iter_idx and not e.get("is_critic", False)]
                
                # If iteration already has enough records, consider whether to record current call
                if len(iter_records) >= 3:  # Maximum 3 non-critic records per iteration
                    # Check if it's an important record (e.g., writing files, executing code, etc.)
                    summary = tool_out.get("summary", "")
                    important = False
                    
                    # Criteria for important records
                    important_tools = ["File_Writer_Tool", "Python_Execution_Tool", "Plotting_Tool"]
                    important_keywords = ["report.md", "execute", "plot", "result", "error", "finish", "complete"]
                    
                    # Check tool name
                    tool_name = ""
                    if isinstance(call_dict, dict):
                        for key in ["tool", "name", "function"]:
                            if key in call_dict:
                                tool_name = str(call_dict[key])
                                break
                    
                    # Check if tool name is important
                    if any(tool in tool_name for tool in important_tools):
                        important = True
                    
                    # Check if summary contains important keywords
                    if any(keyword in summary for keyword in important_keywords):
                        important = True
                    
                    # If not important and already have enough records, skip
                    if not important:
                        self._log_print("info", f"Skipping non-important record: iteration {iter_idx} already has {len(iter_records)} records")
                        return True
            # ------------------------------------------------
            
            # Build history entry
            entry = {
                "timestamp": self._utc(),
                "iteration": iter_idx,
                "is_critic": critic,
                "summary": tool_out.get("summary", ""),
                "details": {
                    "call_data": call_dict,
                    "results": tool_out.get("tool_results", {})
                }
            }
            
            # Add to history
            ctx["simulation_history"].append(entry)
            
            # Limit history size, keep last 50 entries
            if len(ctx["simulation_history"]) > 50:
                ctx["simulation_history"] = ctx["simulation_history"][-50:]
                self._log_print("info", "Trimmed simulation_history to last 50 entries")
            
            # Save back to file
            self._save_json(self.sim_context_path, ctx)
            return True
        except Exception as e:
            self._log_print("error", f"Failed to append simulation history entry: {e}")
            return False
    
    def _run_critic(self, messages, grp_root, iter_idx=0):
        """
        Called every critic_interval steps, replaced by _run_critic_generic
        Note: This method is kept for backward compatibility, new code should use _run_critic_generic directly
        
        Args:
            messages: Message list
            grp_root: Group root directory
            iter_idx: Current iteration index
            
        Returns:
            (feedback_text, score)
        """
        question        = self.context_dict.get("modeling_question","")
        data_info       = self._prepare_data_info(os.path.join(grp_root,"data"))
        workspace_info  = self._prepare_workspace_info(grp_root)
        return self._run_critic_generic(
            is_final=False,
            grp_root=grp_root,
            question=question,
            data_info=data_info,
            workspace_info=workspace_info,
            iter_idx=iter_idx
        )
    
    def _run_final_critic(self, messages, grp_root, iter_idx=0):
        """
        Run final evaluation, replaced by _run_critic_generic
        Note: This method is kept for backward compatibility, new code should use _run_critic_generic directly
        
        Args:
            messages: Message list
            grp_root: Group root directory
            iter_idx: Current iteration index
            
        Returns:
            (feedback_text, score)
        """
        question        = self.context_dict.get("modeling_question","")
        data_info       = self._prepare_data_info(os.path.join(grp_root,"data"))
        workspace_info  = self._prepare_workspace_info(grp_root)
        return self._run_critic_generic(
            is_final=True,
            grp_root=grp_root,
            question=question,
            data_info=data_info,
            workspace_info=workspace_info,
            iter_idx=iter_idx
        )
    
    def single_modeling_run(self, group_suffix: str, max_iter: int | None = None, first_attempt: bool = True) -> dict:
        """
        Complete pipeline from initialization → iteration → final evaluation within a modeling_x_x directory,
        and write simulation history/result back to context.json and simulation_history.txt
        
        Args:
            group_suffix: Modeling group suffix, e.g. "0_0", determines which modeling_x_x directory to use
            max_iter: Maximum number of iterations, if None then read from config
            first_attempt: Whether this is the first attempt, default True. Only consider overwrite parameter when first_attempt=True
            
        Returns:
            dict: Dictionary containing run result information
        """
        from src.ModelAgent.utils.utils import form_message
        from src.ModelAgent.prompts.function_call_prompts import MULTI_TOOLS_SCHEMA
        from src.ModelAgent.prompts.simulation_prompts import MODELING_SYS, MODELING_USER, MODELING_EXPERIMENT, MODELING_ANALYSIS
        
        # Check if group exists
        if group_suffix not in self.group_paths:
            self._log_print("error", f"Group suffix '{group_suffix}' not found in available groups")
            return {
                "success": False,
                "score": 0,
                "iterations": 0,
                "group": group_suffix,
                "sim_context_path": None,
                "error": "Group not found"
            }
        
        # ===== 1. Initialization Phase =====
        self.current_group_suffix = group_suffix  # Save current group identifier for logging
        
        # Get group root directory path
        grp_root = self.group_paths[group_suffix]["root"]
        results_dir = os.path.join(grp_root, "results")
        report_path = os.path.join(results_dir, "report.md")
        
        # Check if this subdirectory needs to be rebuilt
        # Only consider overwrite and report.md when first_attempt=True
        if first_attempt and not self.overwrite and os.path.exists(report_path):
            self._log_print("info", f"Skipping simulation for group {group_suffix} as report.md already exists and overwrite=False (first attempt)")
            # Return simulated completed result
            return {
                "success": True,
                "score": -1,  # Indicates not scored but considered successful
                "iterations": 0,
                "group": group_suffix,
                "sim_context_path": os.path.join(grp_root, "context.json"),
                "message": "Simulation skipped due to existing report.md and overwrite=False"
            }
        elif os.path.exists(grp_root) and (not first_attempt or self.overwrite or not os.path.exists(report_path)):
            # If not first attempt, or need to overwrite (overwrite=True or report.md doesn't exist), rebuild this group directory
            reset_reason = "non-first attempt" if not first_attempt else "overwrite=True or no report.md"
            self._log_print("info", f"Recreating directory for group {group_suffix} ({reset_reason})")
            try:
                shutil.rmtree(grp_root)
                # Recreate subdirectories
                subdirs = ["data", "model", "experiments", "results"]
                paths = {"root": grp_root}
                for name in subdirs:
                    dir_path = os.path.join(grp_root, name)
                    os.makedirs(dir_path, exist_ok=True)
                    paths[name] = dir_path
                
                # Update group_paths
                self.group_paths[group_suffix] = paths
                
                # Recopy data
                src_dirs = self._get_data_sources()
                copied_dirs = 0
                copied_files = 0
                
                for src in src_dirs:
                    def _safe_copy(src_path, dst_root):
                        nonlocal copied_dirs, copied_files
                        try:
                            if os.path.isdir(src_path):
                                dst_path = os.path.join(dst_root, os.path.basename(src_path))
                                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                                copied_dirs += 1
                            else:  # File
                                shutil.copy2(src_path, dst_root)
                                copied_files += 1
                        except OSError as e:
                            if "No space left on device" in str(e):
                                raise RuntimeError(f"Insufficient disk space when copying {src_path}")
                            self._log_print("warn", f"Failed to copy {src_path}: {e}")
                    
                    _safe_copy(src, paths["data"])
                
                self._log_print("info", f"Group {group_suffix}: Copied {copied_dirs} dirs, {copied_files} files to {paths['data']}")
            except Exception as e:
                self._log_print("error", f"Error recreating directory for group {group_suffix}: {e}")
                return {
                    "success": False,
                    "score": 0,
                    "iterations": 0,
                    "group": group_suffix,
                    "sim_context_path": None,
                    "error": f"Error recreating directory: {str(e)}"
                }
        
        # Switch working directory to specified group
        os.environ["WORKSPACE_PATH"] = grp_root
        prev_dir = os.getcwd()
        os.chdir(grp_root)
        self._log_print("system", f"Changed working directory to: {grp_root} for group {group_suffix}")
        
        # Generate/read dedicated context.json
        self.sim_context_path = os.path.join(grp_root, "context.json")
        if not os.path.exists(self.sim_context_path):
            self._save_json(self.sim_context_path, {})
            self._log_print("info", f"Created new context.json at {self.sim_context_path}")
        
        # Initialize simulation history text
        self.sim_history_path = os.path.join(grp_root, "simulation_history.txt")
        self._init_sim_history_file()
        
        try:
            # Organize prompt materials
            sim_config = self.config.get("simulation", {})
            critic_interval = sim_config.get("critic_interval", 3)
            threshold = sim_config.get("score_threshold", 12)
            
            # Get necessary content from main context
            question = self.context_dict.get("question", "No question provided")
            modeling_question = self.context_dict.get("modeling_question", "No modeling question provided")
            
            # Format grading_points as JSON string
            grading_points_data = self.context_dict.get("grading_points", [])
            if isinstance(grading_points_data, list):
                # If it's a list, format as structured text
                grading_points = ""
                for i, point in enumerate(grading_points_data):
                    if isinstance(point, dict):
                        category = point.get("category", f"Criteria {i+1}")
                        description = point.get("description", "No description provided")
                        grading_points += f"{i+1}. {category}: {description}\n"
                    else:
                        grading_points += f"{i+1}. {str(point)}\n"
            else:
                # If not a list, use string representation directly
                grading_points = str(grading_points_data)
                
            self._log_print("info", f"Using {len(grading_points_data) if isinstance(grading_points_data, list) else 1} grading points")
            
            # Get factors
            factors_key = self.task_table[group_suffix]["factors_key"]
            factors_list = self.context_dict.get(factors_key, [])
            factors_json = json.dumps(factors_list, indent=2, ensure_ascii=False)
            
            # Scan data files
            data_info = self._prepare_data_info(os.path.join(grp_root, "data"))
            
            # Get workspace file information
            workspace_info = self._prepare_workspace_info(grp_root)
            self._log_print("info", f"Scanned workspace for group {group_suffix}, found files and code")
            
            # Build user prompt (using MODELING_USER template)
            modeling_implementation = "Based on collected data and specified factors"  # Default initial implementation plan
            data_collection_results = data_info  # Use our prepared data information
            
            # Format base prompt using template
            user_prompt = MODELING_USER.format(
                modeling_question=modeling_question,
                modeling_implementation=modeling_implementation,
                factors=factors_json,
                data_collection_results=data_collection_results,
                grading_points=grading_points
            )
            
            # Add workspace file information
            user_prompt += "\n\n## Workspace Files\n" + workspace_info
            
            # Add tool usage hint
            user_prompt += "\n\nYou can use file_reader_tool to read any file in the workspace, especially for files marked as [TRUNCATED]."
            
            # Inject tool schema (using MULTI_TOOLS_SCHEMA from modeling_prompts)
            from src.ModelAgent.prompts.function_call_prompts import MULTI_TOOLS_SCHEMA
            tools_schema = self.tool_handler.inject_tool_metadata(MULTI_TOOLS_SCHEMA)
            
            # Modify system prompt to indicate unavailable tools should not be called
            system_prompt = MODELING_SYS + "\n\nTools marked (NOT AVAILABLE) may not be called."
            
            # Build initial message list
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # ===== 2. Iteration Loop =====
            iter_idx = 0
            finished = False
            score = 0
            max_iterations = max_iter or sim_config.get("max_iter", 10)
            
            # Add counter for tracking consecutive empty tool calls
            consecutive_empty_calls = 0
            
            self._log_print("system", f"Starting simulation run for group {group_suffix}, max_iter={max_iterations}")
            
            while not finished and iter_idx < max_iterations:
                self._log_print("system", f"Starting iteration {iter_idx+1}/{max_iterations} for group {group_suffix}")
                
                # Call LLM
                try:
                    resp = self._call_llm_with_tools(messages, tools_schema)
                except Exception as e:
                    self._log_print("error", f"Failed to call LLM at iteration {iter_idx}: {e}")
                    break
                
                # Parse tool_calls
                msg = resp.choices[0].message
                func_name = None
                call_dict = None
                empty_call = True  # Mark if it's an empty tool call (all tool results are null)
                
                # Check for tool_calls
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    # Add assistant message to history
                    messages.append({
                        "role": msg.role,
                        "content": msg.content or "",
                        "tool_calls": getattr(msg, "tool_calls", None),
                    })
                    
                    # Process all tool_calls - no longer filter by name, process all tool calls
                    tool_recorded = False  # Mark if current iteration has recorded tool call
                    for tool_call in msg.tool_calls:
                        try:
                            # Parse arguments
                            call_args = json.loads(tool_call.function.arguments)
                            
                            # Handle list-type arguments
                            if isinstance(call_args, list):
                                self._log_print("warn", f"Tool {tool_call.function.name} arguments are list, converting")
                                call_args = {str(i): v for i, v in enumerate(call_args)}
                            
                            # Execute tool call
                            self._log_print("tool", f"Executing tool: {tool_call.function.name} for group {group_suffix}")
                            tool_out = self.tool_handler.handle_call(
                                call_args,
                                data_point=None,
                                context_path=self.sim_context_path
                            )
                            
                            # Print tool execution results
                            for tool_name, result in tool_out.get("tool_results", {}).items():
                                if result is not None:
                                    result_str = str(result)
                                    if len(result_str) > 100:
                                        result_str = result_str[:100] + "..."
                                    self._log_print("tool", f"Tool running result: {{{tool_name}: {result_str}}}")
                                    empty_call = False  # If any tool result is not null, set mark to False
                            
                            # Add tool response (new format)
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_call.function.name,
                                "content": json.dumps(tool_out.get("tool_results", {}))
                            })
                            
                            # Record in modeling history
                            self._record_modeling_history(group_suffix, iter_idx, tool_call.function.name, tool_out)
                            
                            # Record in plain-text history
                            with open(self.sim_history_path, "a", encoding="utf-8") as f:
                                summary = tool_out.get("summary", "No summary available")
                                f.write(f"[{self._utc()}] ITER {iter_idx+1} : {summary}\n")
                            
                            # Record in JSON history - only record once per iteration
                            if not tool_recorded:
                                self._append_sim_history_entry(iter_idx, call_args, tool_out)
                                tool_recorded = True
                            
                            # Save func_name for detecting tool calls
                            func_name = tool_call.function.name
                            
                            # Check if complete (end if any tool indicates completion)
                            if tool_out.get("finish", False):
                                # Don't end directly, but immediately call critic evaluation
                                self._log_print("info", f"Tool indicated finish=True at iteration {iter_idx+1} for group {group_suffix}, running critic evaluation")
                                
                                # Add a critic evaluation to assess current progress
                                if iter_idx > 0:  # Ensure critic doesn't run on first iteration
                                    # Get latest workspace and data information
                                    workspace_info = self._prepare_workspace_info(grp_root)
                                    data_info = self._prepare_data_info(os.path.join(grp_root, "data"))
                                    critic_fb, critic_score = self._run_critic_generic(
                                        is_final=False,
                                        grp_root=grp_root,
                                        question=question,
                                        data_info="",  # Don't pass data info
                                        workspace_info=workspace_info,
                                        iter_idx=iter_idx
                                    )
                                    messages.append({
                                        "role": "system",
                                        "content": critic_fb
                                    })
                                    score = critic_score
                                    
                                    # If score exceeds threshold, end iteration immediately
                                    if score >= threshold:
                                        self._log_print("info", f"Finish=True and score {score} ≥ threshold {threshold}, ending iterations")
                                        finished = True
                                    else:
                                        self._log_print("info", f"Score {score} < threshold {threshold}, continuing despite finish=True")
                                        messages.append({
                                            "role": "system",
                                            "content": "Even though you've indicated completion, your solution needs further improvement based on the critique. Please refine your model."
                                        })
                                else:
                                    # If it's first iteration, still end run
                                    finished = True
                                    self._log_print("info", f"Simulation finished at iteration 1 (tool_out.finish=True) for group {group_suffix}")
                                
                        except Exception as e:
                            self._log_print("error", f"Error processing tool call {tool_call.function.name}: {e}")
                            # Even if execution fails, add a paired response to avoid 400 error
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_call.function.name,
                                "content": json.dumps({"error": str(e)})
                            })
                    
                # Check for old-style function_call and convert to new format
                elif hasattr(msg, "function_call") and msg.function_call:
                    # Compatible with old format
                    self._log_print("warn", "Using old-style function_call, attempting to convert to tool format")
                    
                    func_name = msg.function_call.name
                    try:
                        # Parse arguments
                        call_args = json.loads(msg.function_call.arguments)
                        
                        # Handle list-type arguments
                        if isinstance(call_args, list):
                            self._log_print("warn", f"Tool {func_name} arguments are list, converting")
                            call_args = {str(i): v for i, v in enumerate(call_args)}
                        
                        # Add assistant message, but convert to tool_calls format
                        tool_call_id = f"call_{int(time.time())}_{iter_idx}"
                        messages.append({
                            "role": msg.role,
                            "content": msg.content or "",
                            "tool_calls": [{
                                "id": tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": func_name,
                                    "arguments": msg.function_call.arguments
                                }
                            }]
                        })
                        
                        # Execute tool call
                        self._log_print("tool", f"Executing tool: {func_name} for group {group_suffix}")
                        tool_out = self.tool_handler.handle_call(
                            call_args,
                            data_point=None,
                            context_path=self.sim_context_path
                        )
                        
                        # Print tool execution results
                        for tool_name, result in tool_out.get("tool_results", {}).items():
                            if result is not None:
                                result_str = str(result)
                                if len(result_str) > 100:
                                    result_str = result_str[:100] + "..."
                                self._log_print("tool", f"Tool running result: {{{tool_name}: {result_str}}}")
                        
                        # Add tool response (new format)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": func_name,
                            "content": json.dumps(tool_out.get("tool_results", {}))
                        })
                        
                        # Record in modeling history
                        self._record_modeling_history(group_suffix, iter_idx, func_name, tool_out)
                        
                        # Record in plain-text history
                        with open(self.sim_history_path, "a", encoding="utf-8") as f:
                            summary = tool_out.get("summary", "No summary available")
                            f.write(f"[{self._utc()}] ITER {iter_idx+1} : {summary}\n")
                        
                        # Record in JSON history - only record first tool call of iteration
                        if not tool_recorded:  # Use previously defined variable
                            self._append_sim_history_entry(iter_idx, call_args, tool_out)
                            tool_recorded = True
                        
                        # Check if complete
                        if tool_out.get("finish", False):
                            finished = True
                            self._log_print("info", f"Simulation finished at iteration {iter_idx+1} (tool_out.finish=True) for group {group_suffix}")
                    
                    except Exception as e:
                        self._log_print("error", f"Failed to parse or execute function call: {e}")
                        # Try to add failure message
                        messages.append({
                            "role": msg.role,
                            "content": msg.content or ""
                        })
                        # Don't set func_name, will trigger retry logic
                else:
                    # No tool calls, just add regular message
                    messages.append({
                        "role": msg.role,
                        "content": msg.content or ""
                    })
                
                # After processing all tool_calls, check if it was an empty call
                if empty_call:
                    consecutive_empty_calls += 1
                    self._log_print("warn", f"Empty tool call detected (all tools returned null), count: {consecutive_empty_calls}/3")
                    
                    # If three consecutive empty calls, add warning message and continue iteration
                    if consecutive_empty_calls >= 3:
                        self._log_print("warn", f"Detected 3 consecutive empty tool calls for group {group_suffix}, but continuing to next iteration")
                        # Add system message to inform model of consecutive call issue
                        messages.append({
                            "role": "system",
                            "content": "Warning: Your last three tool calls returned no results. Please make sure to provide valid inputs to tools and consider trying a different approach."
                        })
                        # Reset counter to give model another chance
                        consecutive_empty_calls = 0
                else:
                    # If not empty call, reset counter
                    consecutive_empty_calls = 0
                    
                # If no tool call found, append retry prompt
                if not func_name and not finished:
                    func_name, retry_recorded = self._retry_tool_call(messages, tools_schema, iter_idx, group_suffix)
                    
                    # If still no tool call after retry, end entire simulation
                    if not func_name and not finished:
                        self._log_print("error", f"No tool call found after 5 retries for group {group_suffix}")
                        finished = True
                        self._log_print("warn", f"Simulation stopped due to no tool call after 5 retries for group {group_suffix}")
                
                # Check if critic needs to be run
                if iter_idx > 0 and iter_idx % critic_interval == 0:
                    # Get latest workspace and data information
                    workspace_info = self._prepare_workspace_info(grp_root)
                    data_info = self._prepare_data_info(os.path.join(grp_root, "data"))
                    critic_fb, critic_score = self._run_critic_generic(
                        is_final=False,
                        grp_root=grp_root,
                        question=question,
                        data_info="",  # Don't pass data info
                        workspace_info=workspace_info,
                        iter_idx=iter_idx
                    )
                    
                    # Add feedback to messages
                    messages.append({
                        "role": "system",
                        "content": critic_fb
                    })
                    
                    score = critic_score
                    
                    # Check if early stop threshold reached
                    if score >= threshold:
                        if self.auto_early_stop:
                            # Auto early stop mode
                            self._log_print("info", f"Auto early-stop: score {score} ≥ threshold {threshold}")
                            finished = True
                            break  # Immediately exit current iteration loop, enter final phase
                        else:
                            # Non-auto early stop mode, only suggest to model but don't force end
                            self._log_print("info", f"Score {score} ≥ threshold {threshold}, but auto_early_stop=False. Adding suggestion to messages")
                            # Add a system message suggesting model consider ending
                            suggestion_msg = "You have reached a passing score in the critic evaluation. If you believe your solution is complete, you can call a tool with finish=True to end the process. Otherwise, you can continue to refine your solution further."
                            messages.append({
                                "role": "system",
                                "content": suggestion_msg
                            })
            
                # Iteration counter
                iter_idx += 1
            
            # ===== 3. Final Phase =====
            
            # Run final critic
            # Get latest workspace and data information
            workspace_info = self._prepare_workspace_info(grp_root)
            data_info = self._prepare_data_info(os.path.join(grp_root, "data"))
            final_fb, final_score = self._run_critic_generic(
                is_final=True,
                grp_root=grp_root,
                question=question,
                data_info="",  # Don't pass data info
                workspace_info=workspace_info,
                iter_idx=iter_idx
            )
            
            # Record in plain-text history
            with open(self.sim_history_path, "a", encoding="utf-8") as f:
                f.write(f"[{self._utc()}] FINAL : Score {final_score}/15, {'SUCCESS' if final_score >= threshold else 'FAILED'} for group {group_suffix}\n")
            
            # Write simulation_result back to context.json
            ctx = self._load_json(self.sim_context_path)
            simulation_result = {
                "group": group_suffix,
                "success": final_score >= threshold,
                "score": final_score,
                "iterations": iter_idx,
                "history_len": len(ctx.get("simulation_history", [])),
                "feedback": final_fb
            }
            ctx["simulation_result"] = simulation_result
            self._save_json(self.sim_context_path, ctx)
            
            # Also write a copy to top-level context for summary
            self.context_dict[f"simulation_result_{group_suffix}"] = simulation_result
            
            # Restore original working directory
            os.chdir(prev_dir)
            
            # Return result
            return {
                "success": final_score >= threshold,
                "score": final_score,
                "iterations": iter_idx,
                "group": group_suffix,
                "sim_context_path": self.sim_context_path
            }
            
        except Exception as e:
            self._log_print("error", f"Error in single_modeling_run for group {group_suffix}: {e}")
            traceback.print_exc()
            
            # Restore original working directory
            os.chdir(prev_dir)
            
            return {
                "success": False,
                "score": 0,
                "iterations": 0,
                "group": group_suffix,
                "sim_context_path": self.sim_context_path if hasattr(self, "sim_context_path") else None,
                "error": str(e)
            }
    
    def _prepare_data_info(self, data_dir):
        """Prepare data information string for prompt"""
        if not os.path.exists(data_dir):
            return "No data directory found."
        
        info_parts = ["### DATA INFO"]
        
        # Find all files
        for root, dirs, files in os.walk(data_dir):
            for file in files:
                file_path = os.path.join(root, file)
                
                if file.endswith('.md'):
                    try:
                        # Use preview function
                        info_parts.append(self._preview_markdown(file_path))
                    except Exception as e:
                        self._log_print("error", f"Error previewing .md file: {e}")
                        info_parts.append(f"- Error reading {file_path}: {e}")
                
                elif file.endswith('.csv'):
                    try:
                        # Use preview function
                        info_parts.append(self._preview_csv(file_path))
                    except Exception as e:
                        self._log_print("error", f"Error previewing .csv file: {e}")
                        info_parts.append(f"- Error reading {file_path}: {e}")
                else:
                    # Other files only list path
                    try:
                        workspace_root = os.getenv("WORKSPACE_PATH")
                        if workspace_root:
                            rel_path = os.path.relpath(file_path, workspace_root)
                            if rel_path.startswith(".."):
                                rel_path = f"{file_path} [OUTSIDE_WORKSPACE]"
                        else:
                            rel_path = file_path
                        info_parts.append(f"- {rel_path}")
                    except Exception as e:
                        info_parts.append(f"- {file_path}: {e}")
        
        if len(info_parts) == 1:
            info_parts.append("No files found in data directory.")
        
        return "\n".join(info_parts)
    
    def _prepare_workspace_info(self, grp_root: str, max_content_len: int = 2000) -> str:
        """
        List all workspace files; provide preview for .py/.md/.csv files outside data directory
        
        Args:
            grp_root: Workspace root directory path
            max_content_len: Maximum file content length limit, truncate if exceeded
            
        Returns:
            Workspace file information string
        """
        info = ["### WORKSPACE OVERVIEW"]
        
        # Skip these file types that may contain binary data or be too large
        skip_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', 
                          '.zip', '.tar', '.gz', '.rar', '.7z', 
                          '.exe', '.dll', '.so', '.bin', '.dat',
                          '.model', '.pkl', '.joblib', '.h5', '.weights'}
        
        try:
            for root, dirs, files in os.walk(grp_root):
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    # Check file size, skip large files
                    try:
                        file_size = os.path.getsize(file_path)
                        if file_size > 10 * 1024 * 1024:  # Skip files >10MB
                            workspace_root = os.getenv("WORKSPACE_PATH")
                            if workspace_root:
                                rel_path = os.path.relpath(file_path, workspace_root)
                                if rel_path.startswith(".."):
                                    rel_path = f"{file_path} [OUTSIDE_WORKSPACE]"
                            else:
                                rel_path = file_path
                            info.append(f"- {rel_path} [Large file: {file_size/1024/1024:.2f}MB]")
                            continue
                    except Exception as e:
                        self._log_print("error", f"Error checking file size: {e}")
                        continue
                    
                    # Check extension, skip binary files
                    ext = os.path.splitext(file)[1].lower()
                    if ext in skip_extensions:
                        workspace_root = os.getenv("WORKSPACE_PATH")
                        if workspace_root:
                            rel_path = os.path.relpath(file_path, workspace_root)
                            if rel_path.startswith(".."):
                                rel_path = f"{file_path} [OUTSIDE_WORKSPACE]"
                        else:
                            rel_path = file_path
                        info.append(f"- {rel_path} [Binary file]")
                        continue
                    
                    # Get file relative path
                    try:
                        workspace_root = os.getenv("WORKSPACE_PATH")
                        if workspace_root:
                            rel_path = os.path.relpath(file_path, workspace_root)
                            if rel_path.startswith(".."):
                                rel_path = f"{file_path} [OUTSIDE_WORKSPACE]"
                        else:
                            rel_path = file_path
                    except Exception as e:
                        self._log_print("error", f"Error getting relative path: {e}")
                        rel_path = file_path
                    
                    # Handle different file types
                    first_dir = rel_path.split(os.sep)[0] if os.sep in rel_path else rel_path
                    
                    # Exclude files in data directory, provide more detailed preview for other directories
                    if first_dir != "data":
                        if file.endswith('.md'):
                            info.append(self._preview_markdown(file_path, max_content_len))
                        elif file.endswith('.csv'):
                            info.append(self._preview_csv(file_path))
                        elif file.endswith('.py'):
                            try:
                                with open(file_path, "r", encoding="utf-8") as f:
                                    content = f.read()
                                
                                # Check content length, handle long files
                                if len(content) > max_content_len:
                                    snippet = content[:max_content_len]
                                    info.append(f"## {rel_path}\n```python\n{snippet}\n…[TRUNCATED - Use file_reader_tool to read full content]\n```\n\n")
                                else:
                                    info.append(f"## {rel_path}\n```python\n{content}\n```\n\n")
                            except Exception as e:
                                self._log_print("error", f"Error reading Python file: {e}")
                                info.append(f"- {rel_path} [ERROR: {str(e)}]")
                        else:
                            # Other files only list path
                            info.append(f"- {rel_path}")
                    else:
                        # Files in data directory only list path
                        info.append(f"- {rel_path}")
        except Exception as e:
            self._log_print("error", f"Error scanning workspace: {e}")
            info.append(f"Error scanning workspace: {e}")
            
        if len(info) == 1:
            info.append("No files found in workspace.")
            
        return "\n".join(info)
    
    def _init_sim_history_file(self):
        """Initialize simulation_history.txt file"""
        try:
            with open(self.sim_history_path, "w", encoding="utf-8") as f:
                f.write(f"=== Simulation History for Group {self.current_group_suffix} (UTC+0) ===\n")
                f.write(f"[{self._utc()}] Started simulation run\n")
            return True
        except Exception as e:
            self._log_print("error", f"Failed to initialize simulation history file: {e}")
            return False
            
    # ========= Ⅰ. Get recent N complete calls =========
    def _get_recent_function_calls(self, n:int = 5) -> list[dict]:
        """
        Extract the last n complete tool call records from simulation_history.json
        (not the compressed version in messages for token saving),
        for use in critic prompt.
        """
        ctx = self._load_json(self.sim_context_path)
        hist = ctx.get("simulation_history", [])
        
        # Filter out entries of type critic to avoid passing critic history repeatedly
        filtered_hist = [entry for entry in hist if not entry.get("is_critic", False)]
        
        # Deduplicate history entries (based on iteration and summary)
        unique_hist = []
        seen_keys = set()
        
        for entry in filtered_hist:
            # Create a key for deduplication
            iter_num = entry.get("iteration", -1)
            summary = entry.get("summary", "")
            unique_key = f"{iter_num}_{summary}"
            
            # If this key hasn't been seen, add to result
            if unique_key not in seen_keys:
                seen_keys.add(unique_key)
                unique_hist.append(entry)
        
        # Return the last n records
        return unique_hist[-n:] if len(unique_hist) >= n else unique_hist
    
    # ========= Ⅱ. Assemble critic Input (Prompt + Slots) =========
    def _build_critic_input(self, *, is_final: bool, question: str, data_info: str, workspace_info: str, recent_calls: list[dict]) -> tuple[list[dict], list[dict]]:
        """
        Return (messages, functions_schema) - single-stage direct call version
        
        - messages: message list containing system and user prompts
        - functions_schema: appropriate schema selected based on is_final
        """
        
        # Get necessary factors and history from context_dict
        modeling_question = self.context_dict.get("modeling_question", question)
        
        # Get factors
        factors_key = self.task_table.get(self.current_group_suffix, {}).get("factors_key", "factors")
        factors_list = self.context_dict.get(factors_key, [])
        factors_json = json.dumps(factors_list, indent=2, ensure_ascii=False)
        
        # Get modeling history
        history_key = self.task_table.get(self.current_group_suffix, {}).get("history_key")
        modeling_history = ""
        if history_key and history_key in self.context_dict:
            modeling_history = json.dumps(self.context_dict[history_key], indent=2, ensure_ascii=False)
        
        # Try to find md and csv files (excluding data directory)
        md_content = ""
        csv_preview = ""
        try:
            group_root = self.group_paths.get(self.current_group_suffix, {}).get("root", "")
            # Find md and csv files
            for root, _, files in os.walk(group_root):
                # Skip data directory
                rel_path = os.path.relpath(root, group_root)
                if rel_path.startswith("data"):
                    continue
                
                for file in files:
                    file_path = os.path.join(root, file)
                    if file.endswith('.md'):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            md_content += f"## {file}\n{f.read()}\n\n"
                    elif file.endswith('.csv'):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            preview_lines = []
                            for i, line in enumerate(f):
                                if i >= 10:  # Only read first 10 lines
                                    break
                                preview_lines.append(line)
                            csv_preview += f"## {file} (first 10 lines)\n```\n{''.join(preview_lines)}\n```\n\n"
        except Exception as e:
            self._log_print("warn", f"Error reading MD/CSV files: {e}")
        
        # Get modeling implementation info (from context or synthesize)
        modeling_implementation = self.context_dict.get("modeling_implementation", "")
        if not modeling_implementation:
            # Build from previous_results or use other means
            modeling_implementation = f"Based on the question '{modeling_question}' and factors provided."
        
        # Decide which evaluation method to use based on is_final
        if is_final:
            # Final evaluation uses simulation evaluation
            CRITIC_SYS = MODELING_CRITIC_SYS
            CRITIC_USER = MODELING_CRITIC_USER
            
            # Use replace instead of format for placeholders
            critic_user_msg = CRITIC_USER
            critic_user_msg = critic_user_msg.replace("<<data_point_to_collect>>", modeling_question)
            critic_user_msg = critic_user_msg.replace("<<modeling_history>>", modeling_history)
            critic_user_msg = critic_user_msg.replace("<<factors>>", factors_json)
            critic_user_msg = critic_user_msg.replace("<<recent_function_calls>>", json.dumps(recent_calls, indent=2, ensure_ascii=False))
            critic_user_msg = critic_user_msg.replace("<<data_collected_so_far>>", "")  # Ensure no data info is passed
            critic_user_msg = critic_user_msg.replace("<<workspace_content>>", workspace_info)
            critic_user_msg = critic_user_msg.replace("<<md_file_content>>", md_content)
            critic_user_msg = critic_user_msg.replace("<<csv_file_preview>>", csv_preview)
        else:
            # Intermediate evaluation uses modeling evaluation
            CRITIC_SYS = MODELING_CRITIC_SYS
            CRITIC_USER = MODELING_CRITIC_USER
            
            critic_user_msg = CRITIC_USER
            critic_user_msg = critic_user_msg.replace("<<data_point_to_collect>>", modeling_question)
            critic_user_msg = critic_user_msg.replace("<<modeling_history>>", modeling_history)
            critic_user_msg = critic_user_msg.replace("<<factors>>", factors_json)
            critic_user_msg = critic_user_msg.replace("<<recent_function_calls>>", json.dumps(recent_calls, indent=2, ensure_ascii=False))
            critic_user_msg = critic_user_msg.replace("<<data_collected_so_far>>", "")  # Ensure no data info is passed
            critic_user_msg = critic_user_msg.replace("<<workspace_content>>", workspace_info)
            critic_user_msg = critic_user_msg.replace("<<md_file_content>>", md_content)
            critic_user_msg = critic_user_msg.replace("<<csv_file_preview>>", csv_preview)
        
        return (
            [
                {"role": "system", "content": CRITIC_SYS},
                {"role": "user", "content": critic_user_msg}
            ],
            MODELING_CRITIQUE_FUNCTION_SCHEMA
        )
    
    # ========= Ⅲ. General critic execution =========
    def _run_critic_generic(self, *, is_final: bool, grp_root:str, question:str,
                            data_info:str, workspace_info:str, iter_idx:int) -> tuple[str,int]:
        """
        Single-stage Critic evaluation:
        1. Call LLM for evaluation and return structured JSON directly
        2. Parse feedback_text and overall_score
        
        Args:
            is_final: Whether it is the final evaluation
            grp_root: Group root directory
            question: Modeling question
            data_info: Data information
            workspace_info: Workspace file information
            iter_idx: Current iteration index
        
        Returns:
            (feedback, score): Evaluation feedback text and total score
        """
        # Define critic_type here in advance to ensure all branches can access
        critic_type = "Final Evaluation" if is_final else "Intermediate Evaluation"

        # -------Prepare input--------
        recent_calls = self._get_recent_function_calls(5)
        msgs, schema = self._build_critic_input(
            is_final=is_final,
            question=question,
            data_info=data_info,
            workspace_info=workspace_info,
            recent_calls=recent_calls
        )
        
        # Extract full system and user messages
        system_message = msgs[0]["content"] if msgs and msgs[0]["role"] == "system" else ""
        user_message = msgs[1]["content"] if len(msgs) > 1 and msgs[1]["role"] == "user" else ""
        critic_mode = "final" if is_final else "intermediate"
        
        # Single-stage call
        resp = self._call_llm_with_tools(
            messages=msgs,
            tools_schema=schema
        )
        
        # Parse tool call result
        tool_msg = resp.choices[0].message
        if not hasattr(tool_msg, "tool_calls") or not tool_msg.tool_calls:
            self._log_print("warn", "Critic did not trigger function call, score 0")
            
            # Use iteration index and critic type to generate unique key for deduplication
            log_key = (iter_idx, is_final)
            
            # Only write to log if this combination has not been recorded
            if log_key not in self.recorded_critic_logs:
                self.recorded_critic_logs.add(log_key)
                
                # Write failure info to simulation_history.txt
                with open(self.sim_history_path, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*80}\n")
                    f.write(f"[{self._utc()}] CRITIC (ITER {iter_idx+1}) - {critic_type} - No function call triggered\n")
                    f.write(f"{'='*80}\n")
                    f.write(f"[System Message]:\n{system_message}\n\n")
                    f.write(f"[User Message]:\n{user_message}\n\n")
                    f.write(f"[Model Response]:\n{tool_msg.content if hasattr(tool_msg, 'content') else 'No output'}\n")
                    f.write(f"{'='*80}\n\n")
            else:
                self._log_print("info", f"Skip duplicate TXT log: iteration {iter_idx+1}, critic_type={critic_type}")
            
            # Record to context.json, use old logic for compatibility
            self._append_sim_history_entry(
                iter_idx, 
                {"critic": True, "mode": critic_mode}, 
                {
                    "summary": "Critic failed to trigger function call", 
                    "tool_results": {},
                    "success": False
                }, 
                critic=True
            )
            
            return "No critique available", 0
    
        try:
            data = json.loads(tool_msg.tool_calls[0].function.arguments)
            raw_response = tool_msg.tool_calls[0].function.arguments
            
            # Get feedback text and total score
            feedback = data.get("feedback_text", "No feedback text provided")
            overall = data["scores"]["overall_score"]
    
            # Log - add detailed output for each score item
            self._log_print("critic", f"Critic overall={overall} | strengths={len(data['strengths'])} | weaknesses={len(data['weaknesses'])}")
            
            # Print details for each score item
            scores = data.get("scores", {})
            if scores:
                score_details = []
                for key, value in scores.items():
                    if key != "overall_score":  # Already printed total score
                        score_details.append(f"{key}={value}")
                if score_details:
                    self._log_print("critic", f"Score details: {' | '.join(score_details)}")
            
            # Use iteration index and critic type to generate unique key for deduplication
            log_key = (iter_idx, is_final)
            
            # Only write to log if this combination has not been recorded
            if log_key not in self.recorded_critic_logs:
                self.recorded_critic_logs.add(log_key)
                
                # Write full input and output to simulation_history.txt
                with open(self.sim_history_path, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*80}\n")
                    f.write(f"[{self._utc()}] CRITIC (ITER {iter_idx+1}) - {critic_type} - Score: {overall}/15\n")
                    f.write(f"{'='*80}\n")
                    # Output full system and user messages
                    f.write(f"[System Message]:\n{system_message}\n\n")
                    f.write(f"[User Message]:\n{user_message}\n\n")
                    f.write(f"[Model Response]:\n{raw_response}\n\n")
                    f.write(f"[Total Score]: {overall}/15\n")
                    
                    # Add score details
                    if scores:
                        f.write("\n[Score Details]:\n")
                        for key, value in scores.items():
                            if key != "overall_score":
                                f.write(f"- {key}: {value}\n")
                    
                    # Add strengths and weaknesses
                    if "strengths" in data and data["strengths"]:
                        f.write("\n[Strengths]:\n")
                        for i, s in enumerate(data["strengths"]):
                            f.write(f"{i+1}. {s}\n")
                    
                    if "weaknesses" in data and data["weaknesses"]:
                        f.write("\n[Weaknesses]:\n")
                        for i, w in enumerate(data["weaknesses"]):
                            f.write(f"{i+1}. {w}\n")
                    
                    # Add feedback text
                    f.write(f"\n[Feedback]:\n{feedback}\n")
                    f.write(f"{'='*80}\n\n")
            else:
                self._log_print("info", f"Skip duplicate TXT log: iteration {iter_idx+1}, critic_type={critic_type}")
            
            # Record to context.json, use old logic for compatibility
            self._append_sim_history_entry(
                iter_idx, 
                {"critic": True, "mode": critic_mode}, 
                {
                    "summary": f"Critic score {overall}", 
                    "tool_results": data,
                    "success": True
                }, 
                critic=True
            )
    
            return feedback, overall
        except Exception as e:
            self._log_print("error", f"Error parsing critic result: {e}")
            
            # Record full input and output to simulation_history.txt in case of error
            raw_response = ""
            try:
                if hasattr(tool_msg, "tool_calls") and tool_msg.tool_calls:
                    raw_response = tool_msg.tool_calls[0].function.arguments
                elif hasattr(tool_msg, "content"):
                    raw_response = tool_msg.content
            except:
                raw_response = "Error extracting response"
            
            # Use iteration index and critic type to generate unique key for deduplication
            log_key = (iter_idx, is_final)
            
            # Only write to log if this combination has not been recorded
            if log_key not in self.recorded_critic_logs:
                self.recorded_critic_logs.add(log_key)
                
                with open(self.sim_history_path, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*80}\n")
                    f.write(f"[{self._utc()}] CRITIC (ITER {iter_idx+1}) - {critic_type} - ERROR\n")
                    f.write(f"{'='*80}\n")
                    f.write(f"[System Message]:\n{system_message}\n\n")
                    f.write(f"[User Message]:\n{user_message}\n\n")
                    f.write(f"[Model Response]:\n{raw_response}\n")
                    f.write(f"[Error Info]: {str(e)}\n")
                    f.write(f"{'='*80}\n\n")
            else:
                self._log_print("info", f"Skip duplicate TXT log: iteration {iter_idx+1}, critic_type={critic_type}")
            
            # Record to context.json, use old logic for compatibility
            self._append_sim_history_entry(
                iter_idx, 
                {"critic": True, "mode": critic_mode}, 
                {
                    "summary": f"Error processing critique: {e}", 
                    "tool_results": {},
                    "success": False
                }, 
                critic=True
            )
            
            return "Error processing critique", 0
    
    def _reset_group_workspace(self, suffix, data_sources=None, first_attempt=False):
        """
        Reset workspace for specified group: check if rebuild is needed based on first_attempt, overwrite and report.md existence
        
        Args:
            suffix: Group suffix
            data_sources: Optional, list of data source paths, if not provided will call _get_data_sources
            first_attempt: Whether this is the first attempt, default False. Only consider overwrite parameter when first_attempt=True
            
        Returns:
            bool: Whether operation was successful
        """
        # Get group root directory
        grp_root = os.path.join(self.sim_root, f"modeling_{suffix}")
        results_dir = os.path.join(grp_root, "results")
        report_path = os.path.join(results_dir, "report.md")
        
        # Check if rebuild is needed
        # Only check overwrite and report.md when first_attempt=True
        if first_attempt and not self.overwrite and os.path.exists(report_path):
            self._log_print("info", f"Skipping reset for group {suffix} as report.md exists and overwrite=False (first attempt)")
            return True
        
        # If not first attempt, or overwrite=True, or report.md doesn't exist, rebuild directory
        if os.path.exists(grp_root):
            try:
                reset_reason = "non-first attempt" if not first_attempt else "overwrite=True or no report.md"
                self._log_print("info", f"Resetting workspace for group {suffix}: {grp_root} ({reset_reason})")
                shutil.rmtree(grp_root)
            except Exception as e:
                self._log_print("warn", f"Failed to remove directory {grp_root}: {e}")
                return False
        
        # 2. Recreate directory structure
        subdirs = ["data", "model", "experiments", "results"]
        paths = {"root": grp_root}
        
        try:
            for name in subdirs:
                dir_path = os.path.join(grp_root, name)
                os.makedirs(dir_path, exist_ok=True)
                paths[name] = dir_path
            
            # 更新group_paths
            self.group_paths[suffix] = paths
        except Exception as e:
            self._log_print("error", f"Failed to recreate directories for group {suffix}: {e}")
            return False
        
        # 3. 复制数据
        if data_sources is None:
            data_sources = self._get_data_sources()
        
        group_data_dir = paths["data"]
        copied_dirs = 0
        copied_files = 0
        
        # 定义安全复制函数
        def _safe_copy(src_path, dst_root):
            nonlocal copied_dirs, copied_files
            try:
                if os.path.isdir(src_path):
                    dst_path = os.path.join(dst_root, os.path.basename(src_path))
                    shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                    copied_dirs += 1
                    return True
                elif os.path.isfile(src_path):
                    shutil.copy2(src_path, dst_root)
                    copied_files += 1
                    return True
                return False
            except OSError as e:
                if "No space left on device" in str(e):
                    raise RuntimeError(f"Insufficient disk space when copying {src_path}")
                self._log_print("warn", f"Failed to copy {src_path}: {e}")
                return False
        
        # 复制所有数据源
        try:
            for src in data_sources:
                if os.path.isdir(src):
                    # 复制目录内容递归
                    for root, dirs, files in os.walk(src):
                        for file in files:
                            src_file = os.path.join(root, file)
                            rel_path = os.path.relpath(src_file, src)
                            dst_file = os.path.join(group_data_dir, rel_path)
                            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                            try:
                                shutil.copy2(src_file, dst_file)
                                copied_files += 1
                            except OSError as e:
                                if "No space left on device" in str(e):
                                    raise RuntimeError(f"Insufficient disk space when copying {src_file}")
                                self._log_print("warn", f"Failed to copy {src_file}: {e}")
                elif os.path.isfile(src):
                    _safe_copy(src, group_data_dir)
            
            self._log_print("info", f"Group {suffix}: Copied {copied_dirs} dirs, {copied_files} files to {paths['data']}")
            return True
        except Exception as e:
            self._log_print("error", f"Failed to copy data for group {suffix}: {e}")
            return False
    
    def _persist_global_context(self):
        """
        Persist context_dict to log_dir/context.json,
        but keep modeling_history unchanged
        
        Returns:
            bool: Whether operation was successful
        """
        try:
            ctx_path = os.path.join(self.log_dir, "context.json")
            
            # First read existing file (if exists)
            existing_ctx = {}
            if os.path.exists(ctx_path):
                try:
                    with open(ctx_path, "r", encoding="utf-8") as f:
                        existing_ctx = json.load(f)
                except Exception as e:
                    self._log_print("warn", f"Failed to read existing context.json: {e}, will overwrite")
            
            # Create a clean dictionary, excluding modeling_history related keys
            clean_ctx = {}
            for k, v in self.context_dict.items():
                # Exclude all keys starting with modeling_history
                if not k.startswith("modeling_history"):
                    clean_ctx[k] = v
            
            # If initial modeling_history values exist, keep them
            for k, v in self.initial_modeling_histories.items():
                # If existing context already has the same key, keep original value
                if k in existing_ctx:
                    clean_ctx[k] = existing_ctx[k]
                # Otherwise use initial value
                else:
                    clean_ctx[k] = v
            
            # Update content and write back
            existing_ctx.update(clean_ctx)
            
            with open(ctx_path, "w", encoding="utf-8") as f:
                json.dump(existing_ctx, f, indent=2, ensure_ascii=False)
            
            self._log_print("info", f"Global context persisted to {ctx_path} (with original modeling_history)")
            return True
        except Exception as e:
            self._log_print("warn", f"Failed to persist global context: {e}")
            return False
    
    def run(self):
        """
        Run all modeling groups sequentially; automatically rebuild workspace and retry on failure
        
        - No parameters, no return value
        - Process each group in task_table order
        - Each group has maximum MAX_RETRY attempts (default 5)
        - All results recorded in context_dict and persisted
        """
        # Read configuration
        sim_config = self.config.get("simulation", {})
        MAX_RETRY = sim_config.get("max_retry_each", 5)
        
        # Record total task overview
        n_groups = len(self.task_table)
        self._log_print("system", f"=== run(): {n_groups} groups ===")
        
        # Pre-fetch data sources
        data_sources = self._get_data_sources()
        self._log_print("info", f"Found {len(data_sources)} data sources for copying")
        
        # Add skip counter variable
        skipped_groups = 0
        
        # Process each group
        for suffix in self.task_table.keys():
            self._log_print("system", f"Processing group '{suffix}'")
            
            # Check if should skip (if overwrite=False and results exist)
            results_dir = os.path.join(self.group_paths[suffix]["root"], "results")
            report_path = os.path.join(results_dir, "report.md")
            if not self.overwrite and os.path.exists(report_path):
                self._log_print("info", f"Skipping group '{suffix}' as report.md already exists and overwrite=False")
                
                # Record skipped result in context_dict
                self.context_dict[f"simulation_result_{suffix}"] = {
                    "group": suffix,
                    "success": True,
                    "score": -1,  # Indicates not scored but considered successful
                    "iterations": 0,
                    "message": "Simulation skipped due to existing report.md and overwrite=False",
                    "skipped": True  # Mark as skipped
                }
                
                # Persist overall context
                self._persist_global_context()
                
                # Increment skip counter
                skipped_groups += 1
                continue
            
            for attempt in range(1, MAX_RETRY + 1):
                # Record attempt count
                self._log_print("info", f"Group '{suffix}': Attempt {attempt}/{MAX_RETRY}")
                
                # If not first attempt, reset workspace
                if attempt > 1:
                    # Only set first_attempt=True for attempt=1, False for others
                    # This ensures overwrite parameter is only considered on first attempt
                    if not self._reset_group_workspace(suffix, data_sources, first_attempt=(attempt == 1)):
                        self._log_print("error", f"Failed to reset workspace for group '{suffix}', skipping")
                        break
                
                # Run single group modeling
                try:
                    # first_attempt=True for first attempt, False for subsequent attempts
                    result = self.single_modeling_run(suffix, first_attempt=(attempt == 1))
                    
                    # Record attempt count
                    result["attempt"] = attempt
                    
                    # Store result in context_dict
                    self.context_dict[f"simulation_result_{suffix}"] = result
                    
                    # Persist overall context
                    self._persist_global_context()
                    
                    # Check if successful
                    if result.get("success", False):
                        self._log_print("system", f"Group '{suffix}' succeeded on attempt {attempt}")
                        break
                    else:
                        reason = result.get("error", "score below threshold")
                        self._log_print("info", f"Group '{suffix}' failed on attempt {attempt}: {reason}")
                        
                        # If reached max attempts, record final failure
                        if attempt == MAX_RETRY:
                            self._log_print("warn", f"Group '{suffix}' failed after {MAX_RETRY} attempts")
                except Exception as e:
                    # Catch exception
                    error_msg = str(e)
                    self._log_print("error", f"Exception running group '{suffix}' (attempt {attempt}): {e}")
                    
                    # Record exception info in context_dict
                    self.context_dict[f"simulation_result_{suffix}"] = {
                        "group": suffix,
                        "success": False,
                        "score": 0,
                        "iterations": 0,
                        "attempt": attempt,
                        "error": error_msg
                    }
                    
                    # Persist overall context
                    self._persist_global_context()
                    
                    # Write error log
                    error_log_path = os.path.join(self.group_paths.get(suffix, {}).get("root", self.sim_root), "error.log")
                    try:
                        with open(error_log_path, "w", encoding="utf-8") as f:
                            f.write(f"Error on attempt {attempt}:\n{error_msg}\n\n")
                            f.write(traceback.format_exc())
                    except Exception as log_e:
                        self._log_print("warn", f"Failed to write error log: {log_e}")
        
        # Generate summary report
        self._generate_summary()
        
        # Final persist of context_dict
        self._persist_global_context()
        
        self._log_print("system", "All simulation groups completed")
    
    def _generate_summary(self):
        """Generate summary report to simulation/summary.txt"""
        summary_path = os.path.join(self.sim_root, "summary.txt")
        
        try:
            results = []
            skipped_groups = 0
            
            # Collect results from all groups
            for suffix in self.task_table.keys():
                result_key = f"simulation_result_{suffix}"
                if result_key in self.context_dict:
                    result = self.context_dict[result_key]
                    results.append(result)
                    if result.get("skipped", False):
                        skipped_groups += 1
            
            # Write summary file
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(f"=== Simulation Summary ({self._utc()}) ===\n\n")
                
                # Basic statistics
                f.write(f"Total groups: {len(results)}\n")
                successful_groups = sum(1 for r in results if r.get("success", False))
                f.write(f"Successful groups: {successful_groups}/{len(results)}\n")
                f.write(f"Skipped groups (with existing results): {skipped_groups}/{len(results)}\n")
                
                # Score statistics - exclude skipped groups
                scores = [r.get("score", 0) for r in results if r.get("success", False) and not r.get("skipped", False)]
                if scores:
                    avg_score = sum(scores) / len(scores)
                    max_score = max(scores)
                    min_score = min(scores)
                    f.write(f"Scores (excluding skipped groups): avg={avg_score:.2f}, min={min_score}, max={max_score}\n")
                
                # Detailed results
                f.write("\n=== Detailed Results ===\n\n")
                for r in results:
                    suffix = r.get("group", "unknown")
                    status = "SUCCESS" if r.get("success", False) else "FAILED"
                    score = r.get("score", 0)
                    iters = r.get("iterations", 0)
                    attempt = r.get("attempt", 1)
                    
                    f.write(f"Group {suffix}: {status}\n")
                    
                    # For skipped groups, show special info
                    if r.get("skipped", False):
                        f.write(f"  Status: SKIPPED (existing report.md found)\n")
                    else:
                        f.write(f"  Score: {score}/15\n")
                        f.write(f"  Iterations: {iters}\n")
                        f.write(f"  Attempts: {attempt}\n")
                    
                    if not r.get("success", False):
                        error = r.get("error", "Unknown error")
                        f.write(f"  Error: {error}\n")
                    
                    f.write("\n")
                
                # Last update time
                f.write(f"\nGenerated at: {self._utc()}\n")
            
            self._log_print("system", f"Summary report written to {summary_path}")
            return True
        except Exception as e:
            self._log_print("error", f"Failed to generate summary: {e}")
            return False
    
    def _preview_markdown(self, file_path, md_max_chars=2000):
        """
        Generate markdown preview, include relative path and content snippet
        
        Args:
            file_path: Absolute path to the file
            md_max_chars: Maximum preview characters, default 2000
            
        Returns:
            Formatted preview string
        """
        try:
            # Get path relative to workspace
            workspace_root = os.getenv("WORKSPACE_PATH")
            if workspace_root:
                rel_path = os.path.relpath(file_path, workspace_root)
                # If path is outside workspace, add marker
                if rel_path.startswith(".."):
                    rel_path = f"{file_path} [OUTSIDE_WORKSPACE]"
            else:
                rel_path = file_path
            
            # Read first md_max_chars characters of file content
            with open(file_path, 'r', encoding='utf-8') as f:
                snippet = f.read(md_max_chars)
            
            # Check if truncation marker needed
            if len(snippet) >= md_max_chars:
                snippet += "\n…[TRUNCATED]"
            
            # Construct preview
            return f"## {rel_path}\n```md\n{snippet}\n```\n\n"
        except Exception as e:
            self._log_print("error", f"Error previewing markdown file {file_path}: {e}")
            return f"## {file_path} [ERROR: {str(e)}]\n\n"
    
    def _preview_csv(self, file_path, preview_rows=10):
        """
        Generate CSV preview, include relative path, column names and first few rows of data
        
        Args:
            file_path: Absolute path to the file
            preview_rows: Number of rows to preview (including header), default 10
            
        Returns:
            Formatted preview string
        """
        try:
            import csv
            import itertools
            
            # Get path relative to workspace
            workspace_root = os.getenv("WORKSPACE_PATH")
            if workspace_root:
                rel_path = os.path.relpath(file_path, workspace_root)
                # If path is outside workspace, add marker
                if rel_path.startswith(".."):
                    rel_path = f"{file_path} [OUTSIDE_WORKSPACE]"
            else:
                rel_path = file_path
            
            # Check if has header
            has_header = False
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    sample = f.read(1024)
                    has_header = csv.Sniffer().has_header(sample)
            except:
                has_header = False
            
            # Read CSV data
            rows = []
            header = []
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                
                # Read header
                header = next(reader, [])
                
                # If no real header, first row is data
                if not has_header and header:
                    rows.append(header)
                    header = []
                
                # Read remaining rows
                rows.extend(list(itertools.islice(reader, preview_rows - (1 if has_header else 0))))
            
            # If no header but has data, generate column names
            if not header and rows and rows[0]:
                header = [f"col_{i}" for i in range(len(rows[0]))]
            
            # Construct preview content
            preview_lines = []
            if header:
                preview_lines.append(",".join(header))
            for row in rows:
                preview_lines.append(",".join(row))
            
            preview = "\n".join(preview_lines)
            row_count = len(rows) + (1 if has_header else 0)
            col_count = len(header) if header else 0
            
            # Construct preview
            return f"## {rel_path} (first {min(row_count, preview_rows)} rows, {col_count} columns)\n```csv\n{preview}\n```\n\n"
        except Exception as e:
            self._log_print("error", f"Error previewing CSV file {file_path}: {e}")
            return f"## {file_path} [ERROR: {str(e)}]\n\n"
    
    def _record_modeling_history(self, group_suffix, iter_idx, func_name, tool_out):
        """
        Record modeling history to disk (group's context.json), but do not modify global context_dict
        
        Args:
            group_id: Group ID
            history: Modeling history to record
            
        Returns:
            bool: Whether recording was successful
        """
        # Write modeling history to disk
        history_key = self.task_table[group_suffix].get("history_key")
        if history_key:
            # Control history record writing to avoid excessive growth
            # Only record the following cases:
            # 1. All tool calls from first iteration (initial conception)
            # 2. Operations writing to report.md or other important files
            # 3. Python code execution operations
            summary = tool_out.get("summary", "")
            
            # Check if meets recording conditions
            should_record = False
            
            # Record everything in first iteration
            if iter_idx == 0:
                should_record = True
            # Check if important files were written
            elif "report.md" in summary or "report_" in summary:
                should_record = True
            # Check if Python code was executed
            elif "Python_Execution_Tool" in func_name or "_execution_" in func_name.lower():
                should_record = True
            # Important tool calls
            elif func_name in ["File_Writer_Tool", "Plotting_Tool"]:
                should_record = True
                
            # If conditions not met, return directly
            if not should_record:
                return
                
            # Build summary entry
            summary_entry = {
                "iter": iter_idx,
                "tool": func_name,
                "summary": summary,
                "ts": self._utc()
            }
            
            # Read group's context.json and update
            ctx = self._load_json(self.sim_context_path)
            if history_key not in ctx:
                ctx[history_key] = []
            
            # Update modeling history
            context["modeling_history"] = history
            
            # Limit history size, keep last 20 entries
            if len(ctx[history_key]) > 20:
                ctx[history_key] = ctx[history_key][-20:]
                
            # Save back to file
            self._save_json(self.sim_context_path, ctx)
    
    # _optimize_messages_for_length is located here

    # Add this helper function for handling tool call retries
    def _retry_tool_call(self, messages, tools_schema, iter_idx, group_suffix):
        """
        Handle tool call retry logic, avoid accumulating retry messages in original message list
        
        Args:
            messages: Current message list
            tools_schema: Tool schema
            iter_idx: Current iteration index
            group_suffix: Group suffix
            
        Returns:
            (func_name, tool_recorded): Returns function name and whether recorded on success, (None, False) on failure
        """
        max_retries = 5
        
        for retry_count in range(1, max_retries + 1):
            self._log_print("warn", f"No tool call found, retry {retry_count}/{max_retries} for group {group_suffix}")
            
            # Create copy of retry message list to avoid modifying original messages
            retry_messages = messages.copy()
            retry_messages.append({
                "role": "system", 
                "content": "You MUST use the multi_tools_executor tool to proceed. Do not respond with plain text."
            })
            
            # Retry LLM call
            try:
                resp = self._call_llm_with_tools(retry_messages, tools_schema)
                msg = resp.choices[0].message
                
                # Check for tool calls
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    # Handle tool calls using original code logic
                    for tool_call in msg.tool_calls:
                        try:
                            # Parse arguments
                            call_args = json.loads(tool_call.function.arguments)
                            
                            # Handle list-type parameters
                            if isinstance(call_args, list):
                                self._log_print("warn", f"Tool {tool_call.function.name} parameters are list, converting")
                                call_args = {str(i): v for i, v in enumerate(call_args)}
                            
                            # Execute tool call
                            self._log_print("tool", f"Executing tool: {tool_call.function.name} for group {group_suffix}")
                            tool_out = self.tool_handler.handle_call(
                                call_args,
                                data_point=None,
                                context_path=self.sim_context_path
                            )
                            
                            # Print tool execution results
                            for tool_name, result in tool_out.get("tool_results", {}).items():
                                if result is not None:
                                    result_str = str(result)
                                    if len(result_str) > 100:
                                        result_str = result_str[:100] + "..."
                                    self._log_print("tool", f"Tool running result: {{{tool_name}: {result_str}}}")
                            
                            # Record to modeling history
                            self._record_modeling_history(group_suffix, iter_idx, tool_call.function.name, tool_out)
                            
                            # Record to plain-text history
                            with open(self.sim_history_path, "a", encoding="utf-8") as f:
                                summary = tool_out.get("summary", "No summary available")
                                f.write(f"[{self._utc()}] ITER {iter_idx+1} : {summary}\n")
                            
                            # Record to JSON history
                            self._append_sim_history_entry(iter_idx, call_args, tool_out)
                            
                            # Check if finished
                            if tool_out.get("finish", False):
                                self._log_print("info", f"Simulation finished at iteration {iter_idx+1} (tool_out.finish=True) for group {group_suffix}")
                            
                            # Add messages to original message list
                            messages.append({
                                "role": msg.role,
                                "content": msg.content or "",
                                "tool_calls": getattr(msg, "tool_calls", None)
                            })
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_call.function.name,
                                "content": json.dumps(tool_out.get("tool_results", {}))
                            })
                            
                            # Return function name and whether recorded
                            return tool_call.function.name, True
                            
                        except Exception as e:
                            self._log_print("error", f"Error processing tool call {tool_call.function.name}: {e}")
                
                # Check for old-style function_call
                elif hasattr(msg, "function_call") and msg.function_call:
                    func_name = msg.function_call.name
                    try:
                        # Parse arguments
                        call_args = json.loads(msg.function_call.arguments)
                        
                        # Handle list-type parameters
                        if isinstance(call_args, list):
                            self._log_print("warn", f"Tool {func_name} parameters are list, converting")
                            call_args = {str(i): v for i, v in enumerate(call_args)}
                        
                        # Execute tool call
                        self._log_print("tool", f"Executing tool: {func_name} for group {group_suffix}")
                        tool_out = self.tool_handler.handle_call(
                            call_args,
                            data_point=None,
                            context_path=self.sim_context_path
                        )
                        
                        # Print tool execution results
                        for tool_name, result in tool_out.get("tool_results", {}).items():
                            if result is not None:
                                result_str = str(result)
                                if len(result_str) > 100:
                                    result_str = result_str[:100] + "..."
                                self._log_print("tool", f"Tool running result: {{{tool_name}: {result_str}}}")
                        
                        # Record to modeling history
                        self._record_modeling_history(group_suffix, iter_idx, func_name, tool_out)
                        
                        # Record to plain-text history
                        with open(self.sim_history_path, "a", encoding="utf-8") as f:
                            summary = tool_out.get("summary", "No summary available")
                            f.write(f"[{self._utc()}] ITER {iter_idx+1} : {summary}\n")
                        
                        # Record to JSON history
                        self._append_sim_history_entry(iter_idx, call_args, tool_out)
                        
                        # Check if finished
                        if tool_out.get("finish", False):
                            self._log_print("info", f"Simulation finished at iteration {iter_idx+1} (tool_out.finish=True) for group {group_suffix}")
                        
                        tool_call_id = f"call_{int(time.time())}_{iter_idx}"
                        messages.append({
                            "role": msg.role,
                            "content": msg.content or "",
                            "tool_calls": [{
                                "id": tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": func_name,
                                    "arguments": msg.function_call.arguments
                                }
                            }]
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": func_name,
                            "content": json.dumps(tool_out.get("tool_results", {}))
                        })
                        
                        return func_name, True
                        
                    except Exception as e:
                        self._log_print("error", f"Failed to parse or execute function call: {e}")
                        
            except Exception as e:
                self._log_print("error", f"Failed to retry tool call: {e}")
        
        # All retries failed
        return None, False
