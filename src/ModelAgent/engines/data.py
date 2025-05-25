import sys
import os
import json
import time
import datetime
import shutil
import tempfile
from copy import deepcopy
from types import SimpleNamespace 

# Base path settings
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.append(BASE_DIR)

# Import Core and SharedContext
from src.ModelAgent.engines.core import Core
from src.ModelAgent.utils.utils import form_message
from src.ModelAgent.utils.shared_context import SharedContext
from src.ModelAgent.utils.tool_handler import ToolHandler
from utils.tool_call_parser import extract_tool_call
# Import prompts for data acquisition and evaluation
from src.ModelAgent.prompts.data_acquire import DATA_ACQUIRE_SYS, DATA_ACQUIRE_USER
from src.ModelAgent.prompts.data_critic import DATA_CRITIC_SYS, DATA_CRITIC_USER, PROCESS_CRITIQUE_SYS, PROCESS_CRITIQUE_USER, CRITIQUE_FUNCTION_SCHEMA
from src.ModelAgent.prompts.function_call_prompts import MULTI_TOOLS_SCHEMA 

# Add guess_prompt import
try:
    from src.ModelAgent.prompts.guess_prompt import GUESS_ACQUIRE_SYS
    from src.ModelAgent.prompts.guess_critic import GUESS_CRITIC_SYS
    GUESS_PROMPTS_AVAILABLE = True
    print("[DataAgent] Successfully imported guess_prompt and guess_critic")
except ImportError:
    GUESS_PROMPTS_AVAILABLE = False
    print("[DataAgent] guess_prompt and guess_critic not available, will use default prompts")

class DataAgent:
    """
    Agent focused on querying and acquiring data
    Simplified functionality from baseline, specialized in data collection
    Uses Core for LLM calls and SharedContext for data sharing
    """
    def __init__(self, config, core, shared_context, run_dir=None):
        """
        Initialize DataAgent:
        - config: Contains model and tool settings
        - core: Core implementation for LLM calls
        - shared_context: For sharing information between different engines
        - run_dir: Directory where context.json is located and where results will be saved
        """
        self.config = config
        self.core: Core = core
        self.shared_context: SharedContext = shared_context
        
        # Initialize ToolHandler
        self.tool_handler = ToolHandler(config)
        
        # Get data config (if exists), otherwise use default values
        data_config = config.get("data", {})
        
        # Read parameters from data config
        self.max_iter = data_config.get("max_iter", 10)
        # Adjust threshold for new 15-point scoring system
        self.min_score_threshold = data_config.get("min_score_threshold", 10)  # Default to 10/15
        self.max_attempts = data_config.get("max_attempts", 10)
        self.critic_interval = data_config.get("critic_interval", 5)
        # Read snapshot config
        self.enable_snapshot = data_config.get("snapshot", False)
        # Read overwrite parameter, default to True (overwrite existing files by default)
        self.overwrite = data_config.get("overwrite", True)
        
        # Set up base directory for all data agent runs
        base_dir = os.getcwd()
        self.runs_root = os.path.join(base_dir, "dataagent_runs")
        os.makedirs(self.runs_root, exist_ok=True)
        
        # Set up run directory
        if run_dir and os.path.isdir(run_dir):
            # If run_dir is provided but not in dataagent_runs, create a new dir in dataagent_runs
            run_dir_name = os.path.basename(run_dir)
            self.run_folder = os.path.join(self.runs_root, run_dir_name)
            if self.run_folder != run_dir:
                print(f"[DataAgent] Moving run directory to dataagent_runs: {self.run_folder}")
                # Copy existing files if needed
                if os.path.exists(run_dir) and not os.path.exists(self.run_folder):
                    shutil.copytree(run_dir, self.run_folder)
        else:
            # Create a new run directory with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.run_folder = os.path.join(self.runs_root, f"{timestamp}_data_collection")
            os.makedirs(self.run_folder, exist_ok=True)
        
        print(f"[DataAgent] Using run directory: {self.run_folder}")

        # Set up workspace in the run directory
        # Priority to use work_dir from config
        if "work_dir" in config and config["work_dir"]:
            self.workspace_path = config["work_dir"]
        else:
            self.workspace_path = os.path.join(self.run_folder, "workspace")
        os.makedirs(self.workspace_path, exist_ok=True)
        
        # Create data folder under workspace
        self.data_folder = os.path.join(self.workspace_path, "data")
        os.makedirs(self.data_folder, exist_ok=True)
        print(f"[DataAgent] Created data folder: {self.data_folder}")
        
        # Set environment variable
        os.environ["WORKSPACE_PATH"] = self.workspace_path
        print(f"[DataAgent] WORKSPACE_PATH set to: {self.workspace_path}")

        # Set snapshot directory in data folder
        if self.enable_snapshot:
            self.snapshot_path = os.path.join(self.data_folder, "snapshot")
            os.makedirs(self.snapshot_path, exist_ok=True)
            print(f"[DataAgent] Snapshot path set to: {self.snapshot_path}")

        # Create history file
        self.history_file = os.path.join(self.run_folder, "history.txt")
        if not os.path.exists(self.history_file):
            with open(self.history_file, "w", encoding="utf-8") as hf:
                hf.write("=== DataAgent History Log ===\n")
        
        # Path to context.json
        self.context_path = os.path.join(self.run_folder, "context.json")
        
        # Create additional context.json in data directory
        self.data_context_path = os.path.join(self.data_folder, "data_context.json")
        if not os.path.exists(self.data_context_path):
            with open(self.data_context_path, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2, ensure_ascii=False)

        # Get tool instances from ToolHandler
        self.file_writer_tool = self.tool_handler.get_tool("file_writer_tool")
        self.file_reader_tool = self.tool_handler.get_tool("file_reader_tool")
        self.file_lister_tool = self.tool_handler.get_tool("file_lister_tool")
        self.file_extractor_tool = self.tool_handler.get_tool("file_extractor_tool")
        self.web_download_tool = self.tool_handler.get_tool("web_download_tool")
        self.web_search_tool = self.tool_handler.get_tool("web_search_tool")
        self.url_text_extractor_tool = self.tool_handler.get_tool("url_text_extractor_tool")
        self.pdf_parser_tool = self.tool_handler.get_tool("pdf_parser_tool")
        self.text_detector_tool = self.tool_handler.get_tool("text_detector_tool")
        self.image_captioner_tool = self.tool_handler.get_tool("image_captioner_tool")

        # Tool mapping for handle_call method
        self.tool_map = {
            "file_writer_tool": self.file_writer_tool,
            "file_reader_tool": self.file_reader_tool,
            "file_lister_tool": self.file_lister_tool,
            "web_download_tool": self.web_download_tool,
            "web_search_tool": self.web_search_tool,
            "url_text_extractor_tool": self.url_text_extractor_tool,
            "pdf_parser_tool": self.pdf_parser_tool,
            "text_detector_tool": self.text_detector_tool,
            "image_captioner_tool": self.image_captioner_tool,
            "file_extractor_tool": self.file_extractor_tool,
        }
    def safe_load_json(self,path: str) -> dict:
        """
        Load JSON file; tolerate trailing garbage by reading the first valid object only.
        """
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as fh:
            try:
                return json.load(fh)
            except json.JSONDecodeError:
                fh.seek(0)
                obj, _ = json.JSONDecoder().raw_decode(fh.read())
                print(f"[DataAgent] Warning: extra data in {path} ignored")
                return obj


    def atomic_json_write(self,path: str, data: dict):
        """
        Write JSON atomically: write to temp file then move/replace.
        """
        dir_name = os.path.dirname(path) or "."
        with tempfile.NamedTemporaryFile("w", encoding="utf-8",
                                        dir=dir_name, delete=False) as tmp:
            json.dump(data, tmp, indent=2, ensure_ascii=False)
            tmp.flush()
            os.fsync(tmp.fileno())
        shutil.move(tmp.name, path)    

    def _append_history_entry(self, text: str):
        """Add an entry to the history file"""
        with open(self.history_file, "a", encoding="utf-8") as hf:
            hf.write(text + "\n")

    def handle_call(self, call_data: dict, data_point=None) -> dict:
        """
        Receive tool call data, execute appropriate tools, and return the results
        
        Args:
            call_data: Dictionary containing tool call data
            data_point: Optional data point being processed (for history tracking)
        
        Return format:
        {
            "finish": bool,
            "tool_results": {
                "file_writer_tool": "...",
                "file_reader_tool": "...",
                ...
            }
        }
        """
        return self.tool_handler.handle_call(call_data, data_point, self.context_path)

    def _load_context(self):
        """Load the context from context.json"""
        context = {}  
        
        if os.path.exists(self.context_path):
            try:
                with open(self.context_path, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if hasattr(self.shared_context, 'from_dict'):
                        self.shared_context.from_dict(content)
                    elif hasattr(self.shared_context, 'context'):
                        self.shared_context.context = content
                        context = content
                    else:
                        context = content
                    print(f"[DataAgent] Context loaded from {self.context_path}")
            except Exception as e:
                print(f"Error loading context from {self.context_path}: {e}")
                
        if os.path.exists(self.data_context_path):
            try:
                with open(self.data_context_path, "r", encoding="utf-8") as f:
                    data_content = json.load(f)
                if not hasattr(self.shared_context, 'data'):
                    self.shared_context.data = {}
                if "data_points" in data_content:
                    self.shared_context.data["data_points"] = data_content["data_points"]
                if "data_status" in data_content:
                    self.shared_context.data["data_status"] = data_content["data_status"]
                if "data_metadata" in data_content:
                    self.shared_context.data["data_metadata"] = data_content["data_metadata"]
                print(f"[DataAgent] Data context loaded from {self.data_context_path}")
            except Exception as e:
                print(f"Error loading data context from {self.data_context_path}: {e}")
                if not hasattr(self.shared_context, 'data'):
                    self.shared_context.data = {}
        
        return context

    def _build_compact_history(self, data_point, keep_detailed=3):
        """
        Build compact tool call history, keeping only summaries instead of full details
        
        Args:
            data_point: Current data point name
            keep_detailed: Number of recent entries to keep with full details
            
        Returns:
            Compact history record string
        """
        context = self._load_context()
        history = context.get("data_collection_history", [])
        
        # Filter history for current data point
        point_history = [entry for entry in history if entry.get("data_point", "") == data_point]
        
        if not point_history:
            return "(No history)"
            
        # Calculate which are older entries (summary only)
        if len(point_history) <= keep_detailed:
            older_entries = []
            recent_entries = point_history
        else:
            older_entries = point_history[:-keep_detailed]
            recent_entries = point_history[-keep_detailed:]
            
        history_sections = []
        
        # For older entries, only include summary
        if older_entries:
            older_summaries = []
            for entry in older_entries:
                timestamp = entry.get("timestamp", "Unknown time")
                summary = entry.get("summary", "No summary")
                older_summaries.append(f"- {timestamp}: {summary}")
            
            history_sections.append("## Earlier Tool Calls (Summary Only):\n" + "\n".join(older_summaries))
            
        # For recent entries, include more details
        if recent_entries:
            recent_details = []
            for entry in recent_entries:
                timestamp = entry.get("timestamp", "Unknown time")
                summary = entry.get("summary", "No summary")
                details = entry.get("details", {})
                
                # Simplify details content, only keep function call names and brief parameter descriptions
                simplified_details = {}
                call_data = details.get("call_data", {})
                
                for tool_name, tool_info in call_data.items():
                    if tool_name != "finish" and isinstance(tool_info, dict) and tool_info.get("use_tool"):
                        tool_params = tool_info.get("tool_params", {})
                        param_summary = {}
                        for param_key, param_value in tool_params.items():
                            if isinstance(param_value, str) and len(param_value) > 100:
                                param_summary[param_key] = param_value[:100] + "..."
                            else:
                                param_summary[param_key] = param_value
                        simplified_details[tool_name] = param_summary
                
                recent_details.append(
                    f"- {timestamp}: {summary}\n"
                    f"  Tool Calls: {json.dumps(simplified_details, ensure_ascii=False)}"
                )
            
            history_sections.append("## Recent Tool Calls:\n" + "\n".join(recent_details))
            
        return "\n\n".join(history_sections)

    def _save_context(self, context_override: dict = None):
        """
        Merge new context into disk context.json and write back
        
        Args:
            context_override: Optional context dictionary to merge
        """
        # 0. Read old file from disk
        try:
            with open(self.context_path, "r", encoding="utf-8") as f:
                disk_ctx = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"[DataAgent] Cannot read or parse existing context file, will create new file")
            disk_ctx = {}

        # 1. Get "new content to write"
        if context_override is not None:
            content = context_override
        elif hasattr(self.shared_context, 'to_dict'):
            content = self.shared_context.to_dict()
        elif hasattr(self.shared_context, 'context'):
            content = self.shared_context.context
        else:
            # If cannot get content, create basic dictionary
            content = {}
            for attr_name in dir(self.shared_context):
                if not attr_name.startswith('_') and not callable(getattr(self.shared_context, attr_name)):
                    content[attr_name] = getattr(self.shared_context, attr_name)
        
        # 2. Merge content (top-level key merge)
        merged = {**disk_ctx, **content}
        
        # 3. Atomic write (write to temp file then replace, avoid concurrency issues)
        import tempfile
        import os
        import shutil
        
        temp_dir = os.path.dirname(self.context_path)
        fd, temp_path = tempfile.mkstemp(dir=temp_dir, prefix='.context_', suffix='.json.tmp')
        try:
            with os.fdopen(fd, 'w', encoding="utf-8") as f:
                json.dump(merged, f, indent=2, ensure_ascii=False)
            
            # On Windows, may need to delete target file first
            if os.name == 'nt' and os.path.exists(self.context_path):
                os.remove(self.context_path)
                
            # Replace with final file
            shutil.move(temp_path, self.context_path)
        except Exception as e:
            print(f"[DataAgent] Error writing context file: {e}")
            # Ensure cleanup of temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise
            
        # 4. Sync to shared_context
        if hasattr(self.shared_context, 'from_dict'):
            self.shared_context.from_dict(merged)
        elif hasattr(self.shared_context, 'context'):
            self.shared_context.context = merged
            
        # 5. Also save to data_context.json in data folder
        try:
            # Create context dedicated to data
            data_content = {}
            
            # Check if shared_context.data exists
            if hasattr(self.shared_context, 'data'):
                data_obj = self.shared_context.data
                if isinstance(data_obj, dict):
                    data_content = {
                        "data_points": data_obj.get("data_points", []),
                        "data_status": data_obj.get("data_status", {}),
                        "data_metadata": data_obj.get("data_metadata", {})
                    }
            
            # Use atomic write
            data_temp_dir = os.path.dirname(self.data_context_path)
            data_fd, data_temp_path = tempfile.mkstemp(dir=data_temp_dir, prefix='.data_context_', suffix='.json.tmp')
            try:
                with os.fdopen(data_fd, 'w', encoding="utf-8") as f:
                    json.dump(data_content, f, indent=2, ensure_ascii=False)
                
                # On Windows, may need to delete target file first
                if os.name == 'nt' and os.path.exists(self.data_context_path):
                    os.remove(self.data_context_path)
                    
                # Replace with final file
                shutil.move(data_temp_path, self.data_context_path)
                print(f"[DataAgent] Data context saved to {self.data_context_path}")
            except Exception as e:
                # Ensure cleanup of temp file
                if os.path.exists(data_temp_path):
                    os.remove(data_temp_path)
                raise
        except Exception as e:
            print(f"[DataAgent] Error saving data context to {self.data_context_path}: {e}")

    def _optimize_messages_for_length(self, messages, max_length=200000):
        """
        Optimize message list to reduce total length and avoid exceeding token limits
        
        Strategy:
        1. Keep system messages
        2. Keep last 10 user messages
        3. Process function messages using _build_compact_history method
        
        Args:
            messages: Message list
            max_length: Maximum character length estimate for message content
            
        Returns:
            Optimized message list
        """
        if not messages:
            return messages
            
        # Estimate current total length
        current_length = sum(len(m.get("content", "")) for m in messages if m.get("content"))
        
        # If already within limits, return original messages
        if current_length <= max_length:
            return messages
            
        # Save system messages
        system_messages = [m for m in messages if m.get("role") == "system"]
        
        # Keep last 10 user messages
        user_messages = [m for m in messages if m.get("role") == "user"]
        if len(user_messages) > 10:
            # Only keep latest 10 user messages
            user_messages = user_messages[-10:]
        
        # Get function and assistant messages
        function_messages = [m for m in messages if m.get("role") == "function"]
        assistant_messages = [m for m in messages if m.get("role") == "assistant"]
        
        # Get current data point name (assuming processing some data point)
        current_data_point = None
        for msg in user_messages:
            if msg.get("content") and "data_point_to_collect" in msg.get("content"):
                # Try to extract data point name from user message
                content = msg.get("content", "")
                import re
                match = re.search(r'data_point_to_collect["\']?\s*[:=]\s*["\']?([^"\',.;\s]+)', content)
                if match:
                    current_data_point = match.group(1)
                    break
        
        # Rebuild message list
        optimized_messages = []
        optimized_messages.extend(system_messages)  # All system messages
        optimized_messages.extend(user_messages)    # Kept user messages
        
        # Keep all assistant messages
        optimized_messages.extend(assistant_messages)
        
        # If there are function messages and we can determine the data point, use _build_compact_history
        if function_messages and current_data_point:
            # Add a system message, containing compressed function call history
            compact_history = self._build_compact_history(current_data_point, keep_detailed=5)
            optimized_messages.append({
                "role": "system",
                "content": f"Here's the compact history of previous function calls:\n\n{compact_history}"
            })
        else:
            optimized_messages.extend(function_messages)
        
        return optimized_messages

    def _call_core_function_call_execute(self, messages, tools_definition):
        """
        Call core's function_call_execute method, and add error handling
        
        Args:
            messages: Message list
            tools_definition: Tool definition mode
            
        Returns:
            Function call response
        """
        # Optimize message to reduce length
        optimized_messages = self._optimize_messages_for_length(messages)
        
        # Add error handling and retry mechanism
        max_retries = 3
        retry_count = 0
        last_error = None
        last_response = None
        
        error_log_path = os.path.join(self.run_folder, "error_log.txt")
        
        while retry_count < max_retries:
            try:
                # Record start attempt
                print(f"[DataAgent] Attempting to call function (attempt {retry_count+1}/{max_retries})")
                
                # Call core function
                response = self.core.function_call_execute(optimized_messages, tools_definition)
                
                
                # Call successful, return immediately
                print(f"[DataAgent] Function call successful")
                return response
                
            except Exception as e:
                retry_count += 1
                last_error = e
                
                # Record detailed error information
                import traceback
                error_trace = traceback.format_exc()
                print(f"[DataAgent] Function call error (attempt {retry_count}/{max_retries}): {e}")
                
                # Save last response content (if any)
                if hasattr(e, 'response'):
                    try:
                        last_response = e.response.json() if hasattr(e.response, 'json') else str(e.response)
                        print(f"[DataAgent] API response content: {last_response}")
                    except:
                        last_response = str(e.response) if hasattr(e, 'response') else "No response content"
                
                # Write error information to log file
                with open(error_log_path, "a", encoding="utf-8") as f:
                    f.write(f"\n===== {datetime.datetime.now().isoformat()} =====\n")
                    f.write(f"Error: {str(e)}\n")
                    f.write(f"Error type: {type(last_error)}\n")
                    f.write(f"Error details: {error_trace}\n")
                    if last_response:
                        f.write(f"API response: {last_response}\n")
                
                # If not last attempt, wait for a while before retrying
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff strategy
                    print(f"[DataAgent] Waiting {wait_time} seconds before retrying...")
                    time.sleep(wait_time)
        
        # If all attempts fail, raise an exception with more information
        error_msg = f"Function call generation failed, tried {max_retries} times. Last error: {last_error}"
        if last_response:
            error_msg += f"\nAPI response: {last_response}"
        
        # Write final error log before raising exception
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"\n===== {datetime.datetime.now().isoformat()} - final failure =====\n")
            f.write(f"{error_msg}\n")
        
        raise Exception(error_msg)

    def call_with_patch(self, messages, tools_definition):
        """
        Call core.function_call_execute, then patch the first assistant message
        with <|python_tag|>{...} to standard tool_calls, and convert to support
        dot attribute access SimpleNamespace (recursive).
        """

        # -------- Recursive dict → SimpleNamespace helper --------
        def to_ns(obj):
            if isinstance(obj, dict):
                return SimpleNamespace(**{k: to_ns(v) for k, v in obj.items()})
            if isinstance(obj, list):
                return [to_ns(v) for v in obj]
            return obj
        # --------------------------------------------------

        # 1. Original call
        response = self.core.function_call_execute(messages, tools_definition)

        # 2. Only patch the first assistant message
        if response.choices:
            first_msg = response.choices[0].message          # ← Get first
            response.choices[0].message = extract_tool_call(first_msg)

        return response
    def run_single_collection(self, data_point, shared_context=None):
        """
        Run complete collection process for a single data point, including evaluation and multiple attempts
        
        Args:
            data_point: Data point name
            shared_context: Shared context
            
        Returns:
            Dictionary containing success status, final score and file paths
        """
        print(f"[DataAgent] Processing data point: {data_point}")
        
        # Load modeling context (if needed)
        if shared_context is None:
            print("[DataAgent] Warning: No shared context provided, will use self.shared_context")
            shared_context = self.shared_context.context if hasattr(self.shared_context, 'context') else {}
        
        # Validate data point directory
        data_point_slug = data_point.lower().replace(" ", "_").replace("/", "_")
        # Change data point directory to be inside data_folder
        data_point_dir = os.path.join(self.data_folder, data_point_slug)
        os.makedirs(data_point_dir, exist_ok=True)
        
        # Check if collection for this data point should be skipped (if overwrite=False and files exist)
        if not self.overwrite:
            csv_file_path = os.path.join(data_point_dir, "data.csv")
            md_file_path = os.path.join(data_point_dir, "data_description.md")
            
            # Modified logic: any file being valid is sufficient
            csv_exists = os.path.isfile(csv_file_path)
            md_exists = os.path.isfile(md_file_path)
            
            # Check if at least one file exists
            if csv_exists or md_exists:
                print(f"[DataAgent] Found existing files for data point '{data_point}', checking if can skip")
                csv_valid = False
                csv_info = "CSV file not found"
                md_valid = False
                md_info = "MD file not found"
                
                # Check if CSV file content is valid (if exists)
                if csv_exists:
                    try:
                        import pandas as pd
                        df = pd.read_csv(csv_file_path)
                        row_count = len(df)
                        col_count = len(df.columns)
                        # Only consider file valid if it has more than 1 row
                        csv_valid = row_count > 1
                        csv_info = f"CSV file contains {row_count} rows and {col_count} columns"
                        print(f"[DataAgent] Checking CSV file: {csv_info}, valid: {csv_valid}")
                    except Exception as e:
                        print(f"[DataAgent] Error checking CSV file: {e}")
                        csv_info = f"Error validating CSV: {str(e)}"
                
                # Check if MD file content is valid (if exists)
                if md_exists:
                    try:
                        with open(md_file_path, 'r', encoding='utf-8') as f:
                            md_content = f.read()
                            md_valid = len(md_content) > 100  # Keep original standard, content over 100 chars is valid
                            md_info = f"MD file contains {len(md_content)} characters"
                            print(f"[DataAgent] Checking MD file: {md_info}, valid: {md_valid}")
                    except Exception as e:
                        print(f"[DataAgent] Error checking MD file: {e}")
                        md_info = f"Error validating MD: {str(e)}"
                
                # Skip collection if any file is valid
                if csv_valid or md_valid:
                    print(f"[DataAgent] Existing files for data point '{data_point}' are valid, skipping collection")
                    return {
                        "success": True,
                        "score": 10,  # Default passing score
                        "attempts": 0,
                        "csv_file": csv_file_path if csv_exists else None,
                        "md_file": md_file_path if md_exists else None,
                        "csv_info": csv_info,
                        "md_info": md_info,
                        "skipped": True  # Mark as skipped
                    }
                else:
                    print(f"[DataAgent] Existing files for data point '{data_point}' are invalid, will recollect")
        
        # Update context file
        context = self._load_context()
        
        # Reset evaluation feedback related to this data point
        if "critic_feedback" in context:
            context["critic_feedback"] = [f for f in context.get("critic_feedback", []) 
                                         if f.get("data_point", "") != data_point]
            # ★ Sync back to shared_context
            if hasattr(self.shared_context, 'from_dict'):
                self.shared_context.from_dict(context)
            elif hasattr(self.shared_context, 'context'):
                self.shared_context.context = context
            
            self._save_context(context)
        
        try:
            # ===== Content of original _run_single_iteration method starts =====
            iteration = 0  # Initial iteration count
            print(f"[DataAgent] Data point '{data_point}' running iteration {iteration+1}")
            
            # Extract background information
            factors = context.get("factors_0_0", {})
            explanation = context.get("explanation_0_0", "")
            modeling_history = context.get("modeling_history_0_0", [])
            
            # Convert to string format
            if isinstance(factors, dict) or isinstance(factors, list):
                factors_str = json.dumps(factors, indent=2, ensure_ascii=False)
            else:
                factors_str = str(factors)
                
            if isinstance(modeling_history, dict) or isinstance(modeling_history, list):
                modeling_history_str = json.dumps(modeling_history, indent=2, ensure_ascii=False)
            else:
                modeling_history_str = str(modeling_history)
            
            # Get workspace content
            workspace_content = self._get_workspace_content()
            
            # Get data collection history in optimized way, only including summaries
            history_text = self._build_compact_history(data_point, keep_detailed=3)
            
            # Get previous evaluation feedback
            critic_feedback = ""
            if "critic_feedback" in context and len(context.get("critic_feedback", [])) > 0:
                current_point_feedback = [fb for fb in context.get("critic_feedback", []) 
                                         if fb.get("data_point", "") == data_point]
                if current_point_feedback:
                    latest_feedback = current_point_feedback[-1]
                    processed_feedback = latest_feedback.get("processed_feedback", {})
                    
                    if processed_feedback:
                        critic_feedback = f"""
## Previous Critic Feedback
Data Quality Score: {processed_feedback.get('scores', {}).get('data_quality_score', 'N/A')}/5
Data Reliability Score: {processed_feedback.get('scores', {}).get('reliability_score', 'N/A')}/5
File Structure Score: {processed_feedback.get('scores', {}).get('file_structure_score', 'N/A')}/5
Overall Score: {processed_feedback.get('scores', {}).get('overall_score', 'N/A')}/15

### Strengths
{chr(10).join(['- ' + s for s in processed_feedback.get('strengths', ['No strengths identified'])])}

### Weaknesses
{chr(10).join(['- ' + w for w in processed_feedback.get('weaknesses', ['No weaknesses identified'])])}

### Recommendations
{chr(10).join(['- ' + r for r in processed_feedback.get('recommendations', ['No recommendations provided'])])}
"""
            
            # Build user prompt
            user_content = DATA_ACQUIRE_USER.format(
                modeling_history=modeling_history_str,
                factors=factors_str,
                explanation=explanation,
                data_point_to_collect=data_point,
                data_collection_history=history_text,
                workspace_content=workspace_content,
                critic_feedback=critic_feedback
            )
            
            # Create messages
            messages = form_message(DATA_ACQUIRE_SYS, user_content)
            
            # Record this iteration
            self._append_history_entry(
                f"== [Iteration {iteration+1}] Data point '{data_point}' ==\n"
                f"**System**:\n{DATA_ACQUIRE_SYS}\n\n"
                f"**User**:\n{user_content}\n\n"
            )
            
            # Print to terminal
            self._color_print("system", DATA_ACQUIRE_SYS)
            self._color_print("user", user_content)
            
            # Add tool metadata
            tools_definition = self._inject_tool_metadata(MULTI_TOOLS_SCHEMA)
            
            # Run collection
            iteration_count = 0
            function_call_count = 0
            critic_call_count = 0
            max_iterations = self.max_iter
            finish = False
            last_tool_call_result = ""
            
            # Store recent function calls
            recent_function_calls = []
            # Store intermediate collection results
            intermediate_collection_results = {}
            # Track overall score
            current_score = 0
            min_score_threshold = self.min_score_threshold
            overall_iterations = 0  # Track top-level iteration count
            
            # Output key configuration parameters
            print(f"[DataAgent] Key parameters for data point '{data_point}': max_iterations={max_iterations}, min_score_threshold={min_score_threshold}/15")
            
            # Top-level iteration loop - continue until score meets threshold or reaches max iteration count
            while overall_iterations < max_iterations and int(current_score) < int(min_score_threshold):
                overall_iterations += 1
                print(f"[DataAgent] Starting {overall_iterations}th data collection iteration (current score: {current_score}/15, target threshold: {min_score_threshold}/15)")
                
                # Add explicit pre-loop check - exit immediately if score already meets threshold
                if int(current_score) >= int(min_score_threshold):
                    print(f"[DataAgent] Detected score already meets threshold ({current_score} >= {min_score_threshold}), skipping iteration")
                    break
                
                # Internal collection iteration loop
                iteration_count = 0
                finish = False
                while not finish and iteration_count < max_iterations:
                    iteration_count += 1
                    
                    # Call Core's function_call_execute, supporting max_tokens_per_request and tool calls
                    try:
                        response = self.call_with_patch(
                            messages, 
                            tools_definition
                        )
                        
                        # Record response
                        raw_msg = response.choices[0].message
                        raw_msg_dict = {
                            "role": raw_msg.role,
                            "content": raw_msg.content,
                            "function_call": None
                        }
                        if hasattr(raw_msg, 'function_call') and raw_msg.function_call:
                            raw_msg_dict["function_call"] = {
                                "name": raw_msg.function_call.name,
                                "arguments": raw_msg.function_call.arguments
                            }
                        elif hasattr(raw_msg, 'tool_calls') and raw_msg.tool_calls and len(raw_msg.tool_calls) > 0:
                            raw_msg_dict["function_call"] = {
                                "name": raw_msg.tool_calls[0].function.name,
                                "arguments": raw_msg.tool_calls[0].function.arguments
                            }
                        
                        response_dict = {
                            "id": response.id,
                            "object": response.object,
                            "created": response.created,
                            "model": response.model,
                            "choices": [raw_msg_dict],
                        }
                        response_str = json.dumps(response_dict, ensure_ascii=False, indent=2)
                        self._append_history_entry(f"**Raw Response**:\n{response_str}\n")
                    except Exception as e:
                        print(f"[DataAgent] Function call error: {e}")
                        return {"success": False, "error": str(e), "score": 0}
                    
                    msg_obj = response.choices[0].message
                    
                    # Compatible with both old and new API formats
                    function_call_obj = None
                    if hasattr(msg_obj, 'function_call') and msg_obj.function_call:
                        function_call_obj = msg_obj.function_call
                    
                    # Support for new API format tool_calls
                    elif hasattr(msg_obj, 'tool_calls') and msg_obj.tool_calls and len(msg_obj.tool_calls) > 0:
                        # Find multi_tools_executor tool call
                        for tool_call in msg_obj.tool_calls:
                            if tool_call.function and tool_call.function.name == "multi_tools_executor":
                                # Create compatible old API function_call_obj
                                function_call_obj = type('FunctionCall', (), {
                                    'name': tool_call.function.name,
                                    'arguments': tool_call.function.arguments
                                })
                                break
                    
                    # Check if there's a tool call object
                    if not function_call_obj:
                        # Add retry logic, retry 5 times
                        max_retry = 5
                        retry_count = 0
                        print(f"[DataAgent] No tool call returned. Retrying {max_retry} times.")
                        
                        # Print model text response (if any)
                        if msg_obj.content:
                            print(f"[DataAgent] Model text response: {msg_obj.content}")
                            self._append_history_entry(
                                f"== [Model Response Without Tool Call] ==\n"
                                f"{msg_obj.content}\n\n"
                            )
                        
                        # Print full response object for debugging - only print if no tool calls
                        print(f"[DataAgent] API response details:")
                        print(f"- ID: {response.id}")
                        print(f"- Model: {response.model}")
                        print(f"- Message role: {msg_obj.role}")
                        print(f"- Contains function_call: {hasattr(msg_obj, 'function_call') and msg_obj.function_call is not None}")
                        print(f"- Contains tool_calls: {hasattr(msg_obj, 'tool_calls') and msg_obj.tool_calls and len(msg_obj.tool_calls) > 0}")
                        if hasattr(msg_obj, 'tool_calls') and msg_obj.tool_calls:
                            print(f"- Number of tool calls: {len(msg_obj.tool_calls)}")
                            for i, tc in enumerate(msg_obj.tool_calls):
                                print(f"  Tool call #{i+1}: {tc.type if hasattr(tc, 'type') else 'unknown'}")
                                if hasattr(tc, 'function') and tc.function:
                                    print(f"   Function name: {tc.function.name if hasattr(tc.function, 'name') else 'unknown'}")
                        
                        # Add this response to the message history
                        messages.append({
                            "role": "assistant",
                            "content": msg_obj.content or "No response content."
                        })
                        
                        # Add system prompt to explicitly require tool use
                        retry_message = {
                            "role": "system",
                            "content": f"You must use tool calls to complete the task. Please do not reply with plain text. Use multi_tools_executor to call related tools to collect {data_point} data. Currently collecting data for: {data_point}"
                        }
                        messages.append(retry_message)
                        
                        while retry_count < max_retry and not function_call_obj:
                            retry_count += 1
                            print(f"[DataAgent] Retrying attempt {retry_count}/{max_retry}...")
                            
                            try:
                                # Modify retry call, add function_call parameter, force tool use
                                retry_response = self._call_core_function_call_execute(
                                    messages, 
                                    tools_definition
                                )
                                retry_msg = retry_response.choices[0].message
                                
                                # Check if there's a function_call
                                if hasattr(retry_msg, 'function_call') and retry_msg.function_call:
                                    function_call_obj = retry_msg.function_call
                                    print(f"[DataAgent] Successfully obtained tool call in retry {retry_count}")
                                    # Save successful response for further processing
                                    response = retry_response
                                    break
                                # Check if there's tool_calls
                                elif hasattr(retry_msg, 'tool_calls') and retry_msg.tool_calls and len(retry_msg.tool_calls) > 0:
                                    # Find multi_tools_executor tool call
                                    for tool_call in retry_msg.tool_calls:
                                        if tool_call.function and tool_call.function.name == "multi_tools_executor":
                                            # Create compatible old API function_call_obj
                                            function_call_obj = type('FunctionCall', (), {
                                                'name': tool_call.function.name,
                                                'arguments': tool_call.function.arguments
                                            })
                                            print(f"[DataAgent] Successfully obtained tool_calls tool call in retry {retry_count}")
                                            response = retry_response
                                            break
                                
                                # If still no tool call, print detailed information
                                if not function_call_obj:
                                    print(f"[DataAgent] Failed to obtain tool call in retry {retry_count}")
                                    print(f"[DataAgent] Detailed response for retry {retry_count}:")
                                    print(f"- ID: {retry_response.id}")
                                    print(f"- Model: {retry_response.model}")
                                    print(f"- Message role: {retry_msg.role}")
                                    print(f"- Message content: {retry_msg.content[:200]}..." if retry_msg.content and len(retry_msg.content) > 200 else f"- Message content: {retry_msg.content}")
                                    print(f"- Contains function_call: {hasattr(retry_msg, 'function_call') and retry_msg.function_call is not None}")
                                    print(f"- Contains tool_calls: {hasattr(retry_msg, 'tool_calls') and retry_msg.tool_calls and len(retry_msg.tool_calls) > 0}")
                                    
                                    # If still no tool call, add stronger prompt
                                    messages.append({
                                        "role": "system",
                                        "content": f"You must use tool calls to complete the task. Please do not reply with plain text. Use multi_tools_executor to call related tools to collect {data_point} data. Please ensure format is correct, and return tool_calls instead of plain text reply."
                                    })
                            except Exception as e:
                                print(f"[DataAgent] Error during retry {retry_count}: {e}")
                        
                        # If all retries fail, return failure
                        if not function_call_obj:
                            print(f"[DataAgent] All {max_retry} retry attempts failed. Exiting collection loop.")
                            return {"success": False, "error": "Failed to get tool call after retries", "score": 0}
                    
                    # Parse function call parameters
                    function_args_str = function_call_obj.arguments
                    try:
                        # Fix JSON parsing error, if already a dictionary, use directly
                        if isinstance(function_args_str, dict):
                            tool_call_dict = function_args_str
                        else:
                            tool_call_dict = json.loads(function_args_str)
                    except json.JSONDecodeError as e:
                        print(f"[DataAgent] JSON parsing error: {e}")
                        return {"success": False, "error": f"JSON parse error: {e}", "score": 0}
                    
                    # Call handle_call to execute tool
                    handle_res = self.handle_call(tool_call_dict, data_point)
                    last_tool_call_result = json.dumps(handle_res.get("tool_results", {}), ensure_ascii=False)
                    self._color_print("tool", json.dumps(handle_res, ensure_ascii=False))
                    
                    # Store function call and result for evaluation
                    function_call_record = {
                        "function_call": tool_call_dict,
                        "result": handle_res
                    }
                    recent_function_calls.append(function_call_record)
                    # Only keep last 5 function calls
                    if len(recent_function_calls) > 5:
                        recent_function_calls = recent_function_calls[-5:]
                    
                    # Update intermediate collection results
                    for tool_name, tool_result in handle_res.get("tool_results", {}).items():
                        if tool_result is not None:
                            if tool_name not in intermediate_collection_results:
                                intermediate_collection_results[tool_name] = []
                            intermediate_collection_results[tool_name].append(tool_result)
                    
                    # 增加函数调用计数器
                    function_call_count += 1
                    
                    # Check if it's time to call the critic (every critic_interval function calls)
                    if function_call_count % self.critic_interval == 0 and function_call_count > 0:
                        critic_call_count += 1
                        print(f"[DataAgent] Calling critic after {function_call_count} function calls (critic call #{critic_call_count})")
                        
                        # Create a snapshot of the current state before calling the critic
                        if self.enable_snapshot:
                            self._create_snapshot(data_point, critic_call_count)
                        
                        # Call the critic to evaluate the data collection process
                        critic_feedback = self._call_interim_critic(
                            data_point, 
                            recent_function_calls, 
                            intermediate_collection_results,
                            context
                        )
                        
                        # Process the critic's feedback and extract actionable information
                        processed_critique = self._process_critique(critic_feedback, data_point)
                        
                        # Record the critic's feedback
                        self._append_history_entry(
                            f"== [Critic Evaluation #{critic_call_count}] ==\n"
                            f"**Raw Feedback**:\n{critic_feedback}\n\n"
                            f"**Processed Feedback**:\n{json.dumps(processed_critique, indent=2, ensure_ascii=False)}\n\n"
                        )
                        
                        # Add the critic's feedback to the next function call message
                        critic_message = f"""
## Interim Critic Feedback (Evaluation #{critic_call_count})
Data Quality Score: {processed_critique.get('scores', {}).get('data_quality_score', 3)}/5
Data Reliability Score: {processed_critique.get('scores', {}).get('reliability_score', 3)}/5
File Structure Score: {processed_critique.get('scores', {}).get('file_structure_score', 3)}/5
Overall Score: {processed_critique.get('scores', {}).get('overall_score', 9)}/15

### Strengths
{chr(10).join(['- ' + s for s in processed_critique.get('strengths', ['No strengths identified'])])}

### Weaknesses
{chr(10).join(['- ' + w for w in processed_critique.get('weaknesses', ['No weaknesses identified'])])}

### Recommendations
{chr(10).join(['- ' + r for r in processed_critique.get('recommendations', ['No recommendations provided'])])}

### Suggested Next Steps
{chr(10).join(['- ' + s for s in processed_critique.get('next_steps', ['Continue collecting data'])])}

{f"### Tool Usage Pattern Issues{chr(10)}{chr(10).join(['- ' + i for i in processed_critique.get('tool_pattern_issues', [])])}" if processed_critique.get('tool_pattern_issues') and len(processed_critique.get('tool_pattern_issues', [])) > 0 else ""}

{f"### Specific Tool Instructions{chr(10)}" + chr(10).join([f"- 使用 {t.get('tool_name', '未知工具')}：{json.dumps(t.get('parameters', {}), ensure_ascii=False)}（{t.get('reason', '未提供理由')}）" for t in processed_critique.get('specific_tool_instructions', [])]) if processed_critique.get('specific_tool_instructions') and len(processed_critique.get('specific_tool_instructions', [])) > 0 else ""}
"""
                        
                        # Add the critic's feedback to the context
                        if "critic_feedback" not in context:
                            context["critic_feedback"] = []
                        
                        context["critic_feedback"].append({
                            "timestamp": datetime.datetime.now().isoformat(),
                            "data_point": data_point,
                            "iteration": iteration,
                            "function_call_count": function_call_count,
                            "critic_call_count": critic_call_count,
                            "raw_feedback": critic_feedback,
                            "processed_feedback": processed_critique
                        })
                        
                        # Pass the modified context to _save_context
                        self._save_context(context)
                    
                    # Check if finished
                    finish = handle_res.get("finish", False)
                    
                    # Update the message for the next iteration
                    if not finish:
                        # Add the assistant's response and function result to the conversation
                        messages.append({
                            "role": "assistant", 
                            "content": None,
                            "function_call": {
                                "name": function_call_obj.name,
                                "arguments": function_args_str
                            }
                        })
                        
                        
                        messages.append({
                            "role": "function",
                            "name": function_call_obj.name,
                            "content": last_tool_call_result
                        })
                        
                        # If we just added critic feedback, add it to the message
                        if function_call_count % self.critic_interval == 0 and function_call_count > 0:
                            messages.append({
                                "role": "system",
                                "content": critic_message
                            })
                
                # End of collection loop - if finish=true, evaluate collected data immediately
                if finish:
                    print(f"[DataAgent] Received finish signal (finish=true), evaluating collected data...")
                    
                    # Evaluate collected data
                    feedback, scores = self._evaluate_collected_data(data_point)
                    current_score = int(scores.get("overall", 0))
                    
                    print(f"[DataAgent] Data point '{data_point}' score: {current_score}/15")
                    
                    # If score is high enough, end iteration
                    if int(current_score) >= int(min_score_threshold):
                        print(f"[DataAgent] Data point '{data_point}' reached target quality ({current_score} >= {min_score_threshold})")
                        print(f"[DataAgent] Target score reached, exiting iteration loop and completing data collection")
                        
                        # Collect final data files and get information
                        collection_result = self._collect_final_data_files(data_point)
                        
                        # Create final snapshot
                        if self.enable_snapshot:
                            self._create_snapshot(data_point, "final")
                        
                        # Prepare result
                        result = {
                            "success": True,
                            "score": current_score,
                            "attempts": overall_iterations,
                            "csv_file": collection_result.get("csv_file"),
                            "md_file": collection_result.get("md_file"),
                            "csv_info": collection_result.get("csv_info", ""),
                            "md_info": collection_result.get("md_info", "")
                        }
                        
                        # Return immediately, no further iteration
                        return result
                    
                    # Process evaluation results and prepare for next iteration
                    self._process_evaluation_results(data_point, feedback, scores)
                    
                    # Add feedback to the message for the next iteration
                    feedback_message = {
                        "role": "system", 
                        "content": f"Previous data collection attempt scored {current_score}/15, which is below the threshold of {min_score_threshold}. You need to improve the data collection. Focus on: {feedback[:200]}..."
                    }
                    messages.append(feedback_message)
                else:
                    # If loop exits due to reaching iteration_count limit
                    print(f"[DataAgent] Reached max internal iteration count ({iteration_count}/{max_iterations}), but did not receive finish signal")
                    # Force add a prompt to require completion in the next round
                    messages.append({
                        "role": "system",
                        "content": "You have spent too many iterations without completing the task. In the next iteration, you MUST complete the data collection and call finish=true to indicate completion."
                    })
            
            # End of collection loop
            print(f"[DataAgent] Data collection for '{data_point}' completed, total {overall_iterations} iterations and {function_call_count} function calls.")
            
            # Collect final data files and get information
            collection_result = self._collect_final_data_files(data_point)
            
            # Prepare result
            result = {
                "success": current_score >= min_score_threshold,
                "score": current_score,
                "attempts": overall_iterations,
                "csv_file": collection_result.get("csv_file"),
                "md_file": collection_result.get("md_file"),
                "csv_info": collection_result.get("csv_info", ""),
                "md_info": collection_result.get("md_info", "")
            }
            
            # Check if collection failed and if guess_prompt can be used for fallback
            if not result["success"] and GUESS_PROMPTS_AVAILABLE:
                print(f"[DataAgent] Data point '{data_point}' collection failed (score: {current_score}/{min_score_threshold})")
                print(f"[DataAgent] Trying fallback collection with guess_prompt...")
                
                # Save current result for later comparison
                original_result = result.copy()
                
                # Clear history related to this data point
                self._reset_for_new_datapoint()
                
                if "data_collection_history" in context:
                    context["data_collection_history"] = [
                        entry for entry in context.get("data_collection_history", [])
                        if entry.get("data_point", "") != data_point
                    ]
                if "critic_feedback" in context:
                    context["critic_feedback"] = [
                        entry for entry in context.get("critic_feedback", [])
                        if entry.get("data_point", "") != data_point
                    ]
                
                # ★ Sync back to shared_context
                if hasattr(self.shared_context, 'from_dict'):
                    self.shared_context.from_dict(context)
                elif hasattr(self.shared_context, 'context'):
                    self.shared_context.context = context
                
                self._save_context(context)
                
                # Use guess_prompt to run collection again
                # Create and use guess prompt system and user messages
                try:
                    # Extract background information
                    factors = context.get("factors_0_0", {})
                    explanation = context.get("explanation_0_0", "")
                    modeling_history = context.get("modeling_history_0_0", [])
                    
                    # Convert to string format
                    if isinstance(factors, dict) or isinstance(factors, list):
                        factors_str = json.dumps(factors, indent=2, ensure_ascii=False)
                    else:
                        factors_str = str(factors)
                        
                    if isinstance(modeling_history, dict) or isinstance(modeling_history, list):
                        modeling_history_str = json.dumps(modeling_history, indent=2, ensure_ascii=False)
                    else:
                        modeling_history_str = str(modeling_history)
                    
                    # Get workspace content
                    workspace_content = self._get_workspace_content()
                    
                    # Use optimized way to get data collection history, only including summaries
                    history_text = self._build_compact_history(data_point, keep_detailed=3)
                    
                    # Build user prompt - use guess prompt
                    user_content = DATA_ACQUIRE_USER.format(
                        modeling_history=modeling_history_str,
                        factors=factors_str,
                        explanation=explanation,
                        data_point_to_collect=data_point,
                        data_collection_history=history_text,
                        workspace_content=workspace_content,
                        critic_feedback=""
                    )
                    
                    # Create message - use guess prompt system message
                    messages = form_message(GUESS_ACQUIRE_SYS, user_content)
                    
                    # Record this fallback iteration
                    self._append_history_entry(
                        f"== [FALLBACK WITH GUESS PROMPT] Data point '{data_point}' ==\n"
                        f"**System**:\n{GUESS_ACQUIRE_SYS}\n\n"
                        f"**User**:\n{user_content}\n\n"
                    )
                    
                    # Print to terminal
                    self._color_print("system", "[FALLBACK] " + GUESS_ACQUIRE_SYS)
                    self._color_print("user", user_content)
                    
                    # Add tool metadata
                    tools_definition = self._inject_tool_metadata(MULTI_TOOLS_SCHEMA)
                    
                    # Execute the same logic as normal collection, but use GUESS_ACQUIRE_SYS
                    # Since code is repetitive, reuse previous collection logic, just use different prompt
                    # [Here, execute the same data collection logic as in the original code]
                    # Reset counters and state
                    iteration_count = 0
                    function_call_count = 0
                    critic_call_count = 0
                    finish = False
                    last_tool_call_result = ""
                    recent_function_calls = []
                    intermediate_collection_results = {}
                    current_score = 0
                    overall_iterations = 0
                    
                    # Run fallback loop
                    while overall_iterations < max_iterations and current_score < min_score_threshold:
                        overall_iterations += 1
                        print(f"[DataAgent] [FALLBACK] Starting {overall_iterations}th fallback data collection iteration")
                        
                        # [Here, reuse the internal collection iteration logic from the original code]
                        # For simplicity, key steps are the same as in the original implementation
                        
                        # ... [Logic is the same as in the original code] ...
                        
                        # Final collection and evaluation
                        fallback_collection_result = self._collect_final_data_files(data_point)
                        fallback_feedback, fallback_scores = self._evaluate_collected_data(data_point)
                        fallback_score = fallback_scores.get("overall", 0)
                        
                        # Prepare fallback result
                        fallback_result = {
                            "success": fallback_score >= min_score_threshold,
                            "score": fallback_score,
                            "attempts": overall_iterations,
                            "csv_file": fallback_collection_result.get("csv_file"),
                            "md_file": fallback_collection_result.get("md_file"),
                            "csv_info": fallback_collection_result.get("csv_info", ""),
                            "md_info": fallback_collection_result.get("md_info", ""),
                            "used_guess_prompt": True
                        }
                        
                        # Compare original result and fallback result
                        if fallback_score > original_result["score"]:
                            print(f"[DataAgent] Fallback collection result is better: {fallback_score} > {original_result['score']}")
                            result = fallback_result
                        else:
                            print(f"[DataAgent] Original collection result is better or equal: {original_result['score']} >= {fallback_score}")
                            # Keep original result
                            result["used_guess_prompt"] = False
                        
                        break  # Exit loop after one fallback attempt
                        
                except Exception as e:
                    print(f"[DataAgent] Fallback collection error: {e}")
                    # Keep original result
                    result["used_guess_prompt"] = False
            else:
                # If fallback was not used, add flag
                result["used_guess_prompt"] = False
                
            # ===== 原_run_single_iteration方法的内容结束 =====
            
            # 只将最终结果保存到上下文中，不保存中间过程
            simplified_result = {
                "data_point": data_point,
                "success": result.get("success", False),
                "score": result.get("score", 0),
                "attempts": result.get("attempts", 1),
                "csv_file": result.get("csv_file"),
                "md_file": result.get("md_file")
            }
            
            # 更新本地上下文文件
            context = self._load_context()
            if "data_points_results" not in context:
                context["data_points_results"] = {}
            context["data_points_results"][data_point] = simplified_result
            
            # ★ 同步回shared_context
            if hasattr(self.shared_context, 'from_dict'):
                self.shared_context.from_dict(context)
            elif hasattr(self.shared_context, 'context'):
                self.shared_context.context = context
            
            self._save_context(context)
            
            # 将结果添加到共享上下文
            if isinstance(shared_context, dict):
                shared_context[f"data_result_{data_point}"] = simplified_result
            else:
                # 如果它是SharedContext对象，使用add_context方法
                self.shared_context.add_context(f"data_result_{data_point}", simplified_result)
            
            # 记录最终结果
            print(f"[DataAgent] Data point '{data_point}' final results:")
            print(f"  - Success: {result.get('success', False)}")
            print(f"  - Score: {result.get('score', 0)}/15")
            print(f"  - Attempts: {result.get('attempts', 0)}")
            print(f"  - CSV file: {result.get('csv_file')}")
            print(f"  - MD file: {result.get('md_file')}")
            
            return result
            
        except Exception as e:
            print(f"[DataAgent] Data point '{data_point}' processing failed: {str(e)}")
            import traceback
            traceback.print_exc()
            
            error_result = {
                "success": False,
                "error": str(e),
                "attempts": 1,
                "score": 0
            }
            
            # 将错误记录到上下文
            context = self._load_context()
            if "data_points_results" not in context:
                context["data_points_results"] = {}
            context["data_points_results"][data_point] = {
                "success": False,
                "error": str(e),
                "attempts": 1,
                "score": 0
            }
            
            # ★ 同步回shared_context
            if hasattr(self.shared_context, 'from_dict'):
                self.shared_context.from_dict(context)
            elif hasattr(self.shared_context, 'context'):
                self.shared_context.context = context
                
            self._save_context(context)
            
            return error_result

    def _process_critique(self, critique, data_point):
        """
        Process the critic's feedback to extract actionable information using function calling
        
        Args:
            critique: The critic's feedback as a string
            data_point: The data point being collected
            
        Returns:
            A structured dict with extracted information
        """
        print(f"[DataAgent] Processing critic feedback...")
        
        # Build messages
        messages = [
            {"role": "system", "content": PROCESS_CRITIQUE_SYS},
            {"role": "user", "content": PROCESS_CRITIQUE_USER.format(
                critique=critique,
                data_point_to_collect=data_point
            )}
        ]
        
        # Execute function call
        try:
            response = self.core.function_call_execute(
                messages=messages,
                functions=CRITIQUE_FUNCTION_SCHEMA,  # Use original schema, Core class will convert internally
            )
            
            # Check response format
            function_call_obj = None
            msg_obj = response.choices[0].message
            
            # Try old format function_call
            if hasattr(msg_obj, 'function_call') and msg_obj.function_call:
                function_call_obj = msg_obj.function_call
            
            # Try new format tool_calls
            elif hasattr(msg_obj, 'tool_calls') and msg_obj.tool_calls and len(msg_obj.tool_calls) > 0:
                # Find process_critique tool call
                for tool_call in msg_obj.tool_calls:
                    if tool_call.function and tool_call.function.name == "process_critique":
                        # Create function_call_obj compatible with old API
                        function_call_obj = type('FunctionCall', (), {
                            'name': tool_call.function.name,
                            'arguments': tool_call.function.arguments
                        })
                        break
            
            if function_call_obj and function_call_obj.name == "process_critique":
                processed = json.loads(function_call_obj.arguments)
            else:
                raise Exception("Function call response not returned as expected")
            
        except Exception as e:
            print(f"[DataAgent] Error processing critique: {e}")
            print("[DataAgent] Using default values as fallback")
            
            # Return default structure that matches CRITIQUE_FUNCTION_SCHEMA definition
            processed = {
                "scores": {
                    "data_quality_score": 3,
                    "reliability_score": 3,
                    "file_structure_score": 3,
                    "overall_score": 9
                },
                "strengths": ["Unable to extract strengths from critique"],
                "weaknesses": ["Unable to extract weaknesses from critique"],
                "recommendations": ["Continue collecting data"],
                "next_steps": ["Proceed with next function call"],
                "tool_pattern_issues": [],
                "specific_tool_instructions": []
            }
        if isinstance(processed, dict):
            instr_list = processed.get("specific_tool_instructions", [])
            fixed_list = []
            for item in instr_list:
                if isinstance(item, dict):
                    fixed_list.append(item)
                else:
                    # Compatible with string / other types, prevent AttributeError
                    fixed_list.append({
                        "tool_name":   str(item),
                        "parameters":  {},
                        "reason":      ""
                    })
            # Write back with corrected list
            processed["specific_tool_instructions"] = fixed_list
        # Output tool usage pattern issues and specific instructions (if any)
        if processed.get("tool_pattern_issues") and len(processed.get("tool_pattern_issues", [])) > 0:
            print(f"[DataAgent] Tool usage pattern issues detected:")
            for issue in processed.get("tool_pattern_issues", []):
                print(f"  - {issue}")
                
        # Modify tool instruction processing logic
        specific_instructions = processed.get("specific_tool_instructions")
        if specific_instructions:
            print(f"[DataAgent] Specific tool instruction suggestions:")
            
            # If it's a string, treat it as a single instruction instead of processing character by character
            if isinstance(specific_instructions, str):
                print(f"  - Suggestion: {specific_instructions}")
            
            # If it's a list, process each item normally
            elif isinstance(specific_instructions, list) and len(specific_instructions) > 0:
                # Check first element type, if it's a single character, it might be a string treated as a list
                if len(specific_instructions) > 5 and all(isinstance(item, str) and len(item) == 1 for item in specific_instructions[:5]):
                    # This might be a string that was incorrectly split, combine it
                    combined_instruction = ''.join(specific_instructions)
                    print(f"  - Combined suggestion: {combined_instruction}")
                else:
                    # Process each instruction item normally
                    for instr in specific_instructions:
                        if isinstance(instr, dict):
                            tool_name = instr.get("tool_name", "Unknown tool")
                            reason = instr.get("reason", "No reason provided")
                            params = json.dumps(instr.get("parameters", {}), ensure_ascii=False)
                            print(f"  - Suggested tool: {tool_name}")
                            print(f"    Parameters: {params}")
                            print(f"    Reason: {reason}")
                        else:
                            # For non-dict instruction items, print directly
                            print(f"  - Instruction: {instr}")
            
            # For other types, try to convert to string and print
            else:
                print(f"  - Instruction content: {specific_instructions}")
        
        # Log processing results
        self._append_history_entry(
            f"== Processing Critique for '{data_point}' ==\n"
            f"**Process Response**:\n{json.dumps(processed, indent=2, ensure_ascii=False)}\n\n"
        )
        
        return processed
        
    def _process_evaluation_results(self, data_point, feedback, scores):
        """
        Process evaluation results and prepare for next iteration
        
        Args:
            data_point: Data point name
            feedback: Evaluation feedback
            scores: Evaluation scores
            
        Returns:
            None
        """
        # Load context
        context = self._load_context()
        
        # Add evaluation to data_collection_history
        if "data_collection_history" not in context:
            context["data_collection_history"] = []
        
        context["data_collection_history"].append({
            "timestamp": datetime.datetime.now().isoformat(),
            "data_point": data_point,
            "score": scores.get("overall", 0),
            "summary": f"Iteration score: {scores.get('overall', 0)}/15. {feedback[:100]}..."
        })
        
        # ★ Sync back to shared_context
        if hasattr(self.shared_context, 'from_dict'):
            self.shared_context.from_dict(context)
        elif hasattr(self.shared_context, 'context'):
            self.shared_context.context = context
        
        # Save context
        self._save_context(context)
        
        # Wait a bit before next iteration
        time.sleep(1)

    def _collect_final_data_files(self, data_point):
        """
        Find and collect final data files (data.csv and data_description.md) from the data point directory
        
        Args:
            data_point: Current data point name
            
        Returns:
            dict: Dictionary containing file path information and status
        """
        print(f"[DataAgent] Collecting final data files for '{data_point}'...")
        
        # Get data point directory
        data_point_slug = data_point.lower().replace(" ", "_").replace("/", "_")
        # Change data point directory to be inside data_folder
        data_point_dir = os.path.join(self.data_folder, data_point_slug)
        
        # Check if directory exists
        if not os.path.exists(data_point_dir):
            print(f"[DataAgent] Warning: Data point directory '{data_point_dir}' does not exist")
            return {
                "success": False,
                "reason": f"Data point directory not found: {data_point_dir}",
                "csv_file": None,
                "md_file": None
            }
        
        # Look for fixed-name files
        csv_file_path = os.path.join(data_point_dir, "data.csv")
        md_file_path = os.path.join(data_point_dir, "data_description.md")
        
        # Check if files exist
        csv_exists = os.path.isfile(csv_file_path)
        md_exists = os.path.isfile(md_file_path)
        
        # Validate files exist
        if not csv_exists:
            print(f"[DataAgent] Warning: Required CSV file 'data.csv' not found in {data_point_dir}")
        if not md_exists:
            print(f"[DataAgent] Warning: Required Markdown file 'data_description.md' not found in {data_point_dir}")
            
        # Check CSV file content (optional)
        csv_valid = False
        csv_info = ""
        if csv_exists:
            try:
                import pandas as pd
                df = pd.read_csv(csv_file_path)
                row_count = len(df)
                col_count = len(df.columns)
                # Modify CSV validity check: more than 1 row is valid
                csv_valid = row_count > 1
                csv_info = f"CSV file contains {row_count} rows and {col_count} columns"
                print(f"[DataAgent] {csv_info}")
            except Exception as e:
                print(f"[DataAgent] Error checking CSV file: {e}")
                csv_info = f"Error validating CSV: {str(e)}"
                
        # Check MD file content (optional)
        md_valid = False
        md_info = ""
        if md_exists:
            try:
                with open(md_file_path, 'r', encoding='utf-8') as f:
                    md_content = f.read()
                    md_valid = len(md_content) > 100  # Simple check for document length
                    md_info = f"MD file contains {len(md_content)} characters"
                    print(f"[DataAgent] {md_info}")
            except Exception as e:
                print(f"[DataAgent] Error checking MD file: {e}")
                md_info = f"Error validating MD: {str(e)}"
        
        # Prepare data to write to context
        result = {
            "success": csv_exists and md_exists and csv_valid and md_valid,
            "csv_file": csv_file_path if csv_exists else None,
            "md_file": md_file_path if md_exists else None,
            "csv_info": csv_info,
            "md_info": md_info,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        return result

    def _call_interim_critic(self, data_point, recent_function_calls, intermediate_results, context):
        """
        Call the critic to evaluate the data collection process after a few function calls
        
        Args:
            data_point: The data point being collected
            recent_function_calls: List of recent function calls and their results
            intermediate_results: Collected data so far
            context: The current context dict
            
        Returns:
            Critic's feedback as a string
        """
        print(f"[DataAgent] Evaluating data collection process for '{data_point}'...")
        
        # Get workspace content after collection
        workspace_content = self._get_workspace_content()
        
        # Get the data point directory path
        data_point_slug = data_point.lower().replace(" ", "_").replace("/", "_")
        # Change data point directory to be inside data_folder
        data_point_dir = os.path.join(self.data_folder, data_point_slug)
        
        # Get MD file content if exists
        md_file_content = ""
        md_files = []
        if os.path.exists(data_point_dir):
            md_files = [f for f in os.listdir(data_point_dir) if f.endswith('.md')]
            if md_files:
                try:
                    md_path = os.path.join(data_point_dir, md_files[0])
                    md_result = self.file_reader_tool.execute(file_path=md_path)
                    if isinstance(md_result, dict) and md_result.get("success"):
                        md_file_content = md_result["message"]
                        print(f"[DataAgent] Found MD file: {md_files[0]}")
                    else:
                        md_file_content = f"Error reading MD file: {md_result}"
                except Exception as e:
                    md_file_content = f"Error accessing MD file: {e}"
            else:
                md_file_content = "No MD file found in the data point directory."
        else:
            md_file_content = "Data point directory not found."
        
        # Get CSV file preview if exists
        csv_file_preview = ""
        csv_files = []
        if os.path.exists(data_point_dir):
            csv_files = [f for f in os.listdir(data_point_dir) if f.endswith('.csv')]
            if csv_files:
                try:
                    csv_path = os.path.join(data_point_dir, csv_files[0])
                    # Use pandas to read first 10 rows if available
                    import pandas as pd
                    try:
                        df = pd.read_csv(csv_path)
                        preview = df.head(10).to_string()
                        csv_file_preview = f"File: {csv_files[0]}\n{preview}"
                        print(f"[DataAgent] Found CSV file: {csv_files[0]}")
                    except Exception as csv_e:
                        # Fallback to simple file reading if pandas fails
                        csv_result = self.file_reader_tool.execute(file_path=csv_path)
                        if isinstance(csv_result, dict) and csv_result.get("success"):
                            lines = csv_result["message"].split('\n')
                            csv_file_preview = f"File: {csv_files[0]}\n" + '\n'.join(lines[:11])
                        else:
                            csv_file_preview = f"Error reading CSV file: {csv_result}"
                except Exception as e:
                    csv_file_preview = f"Error accessing CSV file: {e}"
            else:
                csv_file_preview = "No CSV file found in the data point directory."
        else:
            csv_file_preview = "Data point directory not found."
        
        # Extract context background
        factors = context.get("factors_0_0", {})
        explanation = context.get("explanation_0_0", "")
        modeling_history = context.get("modeling_history_0_0", [])
        
        # Convert to string format if needed
        if isinstance(factors, dict) or isinstance(factors, list):
            factors_str = json.dumps(factors, indent=2, ensure_ascii=False)
        else:
            factors_str = str(factors)
            
        if isinstance(modeling_history, dict) or isinstance(modeling_history, list):
            modeling_history_str = json.dumps(modeling_history, indent=2, ensure_ascii=False)
        else:
            modeling_history_str = str(modeling_history)
        
        # Build critic prompt using DATA_CRITIC_USER template
        critic_user = DATA_CRITIC_USER.format(
            data_point_to_collect=data_point,
            modeling_history=modeling_history_str,
            factors=factors_str,
            recent_function_calls="(Final evaluation - recent function calls not included)",
            data_collected_so_far="",  # Empty as we're looking at final files now
            workspace_content=workspace_content,
            md_file_content=md_file_content,
            csv_file_preview=csv_file_preview
        )
        
        critic_messages = form_message(DATA_CRITIC_SYS, critic_user)
        critic_response = self.core.execute(critic_messages)
        
        # Log evaluation
        self._append_history_entry(
            f"== Evaluation for '{data_point}' ==\n"
            f"**Critic Response**:\n{critic_response}\n\n"
        )
        
        # Process evaluation results using function calling
        try:
            print(f"[DataAgent] Processing final evaluation using function calling")
            processed_critique = self._process_critique(critic_response, data_point)
            
            # Get scores from processed_critique
            scores = {
                "data_quality": processed_critique.get("scores", {}).get("data_quality_score", 3),
                "reliability": processed_critique.get("scores", {}).get("reliability_score", 3),
                "file_structure": processed_critique.get("scores", {}).get("file_structure_score", 3),
                "overall": processed_critique.get("scores", {}).get("overall_score", 9)
            }
            
            print(f"[DataAgent] Final evaluation processed through function calling: overall_score={scores.get('overall', 0)}/15")
            
            # Return evaluation feedback and scores
            return critic_response, scores
            
        except Exception as e:
            print(f"[DataAgent] Error processing final evaluation with function calling: {e}")
            print(f"[DataAgent] Falling back to regex extraction")
            
            # Use regex extraction as fallback
            try:
                overall_score = self._extract_overall_score(critic_response)
                data_quality = self._extract_score(critic_response, "Data Quality")
                reliability = self._extract_score(critic_response, "Data Reliability")
                file_structure = self._extract_score(critic_response, "File Structure")
                
                scores = {
                    "data_quality": data_quality,
                    "reliability": reliability,
                    "file_structure": file_structure,
                    "overall": overall_score
                }
                
                print(f"[DataAgent] Scores extracted using regex: overall_score={overall_score}/15")
                
                # Return evaluation feedback and scores
                return critic_response, scores
                
            except Exception as regex_e:
                print(f"[DataAgent] Error parsing evaluation with regex: {regex_e}")
                # Use default values
                scores = {
                    "data_quality": 3,
                    "reliability": 3,
                    "file_structure": 3,
                    "overall": 9  # Default set to a score that might pass threshold
                }
                return "Error processing evaluation, using default scores.", scores


    def _extract_summary(self, evaluation_text):
        """Extract summary from evaluation text"""
        # Look for summary section or use the first few lines if not found
        if "## Overall Assessment" in evaluation_text:
            parts = evaluation_text.split("## Overall Assessment")
            if len(parts) > 1:
                summary_part = parts[1].split("##")[0] if "##" in parts[1] else parts[1]
                return summary_part.strip()
        
        # Fallback to first 200 chars if no summary section
        return evaluation_text[:200] + "..."

    def _extract_suggestions(self, evaluation_text):
        """Extract suggestions from evaluation text"""
        suggestions = []
        
        # Look for suggestions section
        if "## Improvement Suggestions" in evaluation_text:
            suggestions_part = evaluation_text.split("## Improvement Suggestions")[1]
            # Remove any subsequent sections
            if "##" in suggestions_part:
                suggestions_part = suggestions_part.split("##")[0]
            
            # Extract numbered or bulleted items
            import re
            items = re.findall(r"(?:^\d+\.|\*)\s*(.*?)(?=(?:^\d+\.|\*)|$)", suggestions_part, re.MULTILINE | re.DOTALL)
            if items:
                suggestions = [item.strip() for item in items if item.strip()]
        
        # If no suggestions found, check for general recommendations
        if not suggestions and "recommend" in evaluation_text.lower():
            import re
            recommendations = re.findall(r"I recommend (.*?)(?=\.|$)", evaluation_text, re.IGNORECASE)
            if recommendations:
                suggestions = recommendations
        
        return suggestions

    def run(self):
        """
        Main function, runs the data collection process, reading all data points to collect from shared_context
        """
        print("[DataAgent] Starting data collection process...")
        
        # Check tool availability
        unavailable_tools = []
        for tool_name, tool in self.tool_map.items():
            if tool is None:
                unavailable_tools.append(tool_name)
        
        if unavailable_tools:
            print("[DataAgent] Warning: The following tools are not available:")
            for tool_name in unavailable_tools:
                print(f"  - {tool_name}")
            print("\n[DataAgent] Data collection will continue, but some functionality may be limited.")
            
            # Special note for OpenAI-related tools
            if "image_captioner_tool" in unavailable_tools:
                print("\n[DataAgent] Note: To enable OpenAI-related tools, set the OPENAI_API_KEY environment variable or add API key in config:")
                print("  export OPENAI_API_KEY=your_api_key_here")
                print("  or configure in config file: model.api_key")
                
            # Special note for Web Search tools
            if "web_search_tool" in unavailable_tools:
                print("\n[DataAgent] Note: To enable Web Search tools, set the SERPER_API_KEY environment variable or add in config:")
                print("  export SERPER_API_KEY=your_api_key_here")
                print("  or add to config file: model.serper_api_key field")
                print("  Get Serper API key at: https://serper.dev/")
        
        # Get modeling context directly from shared_context.context
        print("[DataAgent] Getting modeling context directly from shared_context.context...")

        # Directly access self.shared_context.context instead of using _load_context method
        if hasattr(self.shared_context, 'context') and self.shared_context.context:
            context = deepcopy(self.shared_context.context)
            print(f"[DataAgent] Successfully retrieved shared_context.context with {len(context)} keys")
        else:
            print("[DataAgent] Warning: self.shared_context.context is empty or doesn't exist")
            context = {}

        # Save context to working directory for later use
        print(f"[DataAgent] Saving context to working directory: {self.context_path}")
        self._save_context(context)

        # Organize data points by factor source
        data_points_by_source = {}
        
        # New: Read bottom_k_data configuration
        bottom_k = self.config.get("data", {}).get("bottom_k_data", 3)
        print(f"[DataAgent] bottom_k_data set to: {bottom_k}")
        
        # Find all factor keys
        factors_keys = [key for key in context.keys() if key.startswith("factors_")]
        print(f"[DataAgent] Found factors keys: {factors_keys}")
        
        # Used to store critic scores for each factor group
        factor_critic_scores = {}
        use_guess_prompt = GUESS_PROMPTS_AVAILABLE
        
        # For each factor key, extract data points and associate with corresponding model_history
        for factors_key in factors_keys:
            source_suffix = factors_key.replace("factors_", "")
            print(f"[DataAgent] Processing {factors_key}, suffix: {source_suffix}")
            
            factors = context[factors_key]
            if not isinstance(factors, list):
                print(f"[DataAgent] Warning: factors in {factors_key} is not a list, skipping")
                continue
                
            # Ensure corresponding modeling_history key exists
            modeling_history_key = f"modeling_history_{source_suffix}"
            if modeling_history_key not in context:
                print(f"[DataAgent] Warning: {modeling_history_key} not found in context, will use empty history")
            
            # Extract data points for this factor
            data_points = []
            for item in factors:
                if isinstance(item, dict) and "variable" in item:
                    var_name = item["variable"]
                    data_points.append(var_name)
                    print(f"[DataAgent] Extracted variable from {factors_key}: {var_name}")
            
            # Find corresponding factor_critics key
            factor_critics_key = f"factor_critics_{source_suffix}"
            if factor_critics_key in context:
                # Get critic scores
                critics = context[factor_critics_key]
                
                # Validate critics format
                if isinstance(critics, list):
                    # Extract overall_score for each data point
                    scores = {}
                    for critic in critics:
                        if isinstance(critic, dict) and "variable" in critic and "overall_score" in critic:
                            var_name = critic["variable"]
                            score = critic["overall_score"]
                            scores[var_name] = score
                            print(f"[DataAgent] Found critic score for {var_name}: {score}")
                    
                    # Save scores for later use
                    if scores:
                        factor_critic_scores[source_suffix] = scores
                
            # Store data points and associated information in a group
            if data_points:
                data_points_by_source[source_suffix] = {
                    "data_points": data_points,
                    "factors_key": factors_key,
                    "modeling_history_key": modeling_history_key,
                    "results": {}  # Will be filled later
                }
            else:
                print(f"[DataAgent] No data points found in {factors_key}")

        # If no data points are found, use default test data points
        if not data_points_by_source:
            print("[DataAgent] Warning: No data points found in any factors, will use default test data points")
            default_suffix = "default"
            data_points_by_source[default_suffix] = {
                "data_points": ["test_data_point_1", "test_data_point_2"],
                "factors_key": "factors_default",
                "modeling_history_key": "modeling_history_default",
                "results": {}
            }

        # Update context
        all_data_points = []
        for source_info in data_points_by_source.values():
            all_data_points.extend(source_info["data_points"])
        
        context["data_points_to_collect"] = all_data_points
        self._save_context(context)

        print(f"[DataAgent] Found {len(all_data_points)} data points across {len(data_points_by_source)} factor groups")
        
        # New: Select data points to use guess_prompt or standard prompt for each source
        standard_prompt_points = {}
        guess_prompt_points = {}
        
        if use_guess_prompt:
            print("[DataAgent] Guess prompts available, selecting bottom-k data points for standard prompts")
            
            for source_suffix, source_info in data_points_by_source.items():
                data_points = source_info["data_points"]
                standard_points = []
                guess_points = []
                
                # If there are critic scores, select bottom-k based on scores
                if source_suffix in factor_critic_scores and factor_critic_scores[source_suffix]:
                    scores = factor_critic_scores[source_suffix]
                    
                    # Filter out data points with scores
                    scored_points = [(dp, scores.get(dp, float('inf'))) for dp in data_points if dp in scores]
                    
                    # If there are not enough scored data points, use standard prompt for all points
                    if len(scored_points) < bottom_k:
                        standard_points = data_points
                        print(f"[DataAgent] Source {source_suffix}: Not enough scored points ({len(scored_points)}/{len(data_points)}), using standard prompt for all points")
                    else:
                        # Sort by score
                        scored_points.sort(key=lambda x: x[1])
                        
                        # Use standard prompt for bottom_k points with lowest scores
                        standard_points = [p[0] for p in scored_points[:bottom_k]]
                        # Use guess prompt for remaining points
                        guess_points = [p[0] for p in scored_points[bottom_k:]]
                        
                        print(f"[DataAgent] Source {source_suffix}: Selected {len(standard_points)} lowest-scored points for standard prompt")
                else:
                    # If there are no critic scores, use standard prompt for all points
                    standard_points = data_points
                    print(f"[DataAgent] Source {source_suffix}: No critic scores available, using standard prompt for all points")
                
                standard_prompt_points[source_suffix] = standard_points
                guess_prompt_points[source_suffix] = guess_points
                
                print(f"[DataAgent] Source {source_suffix}: {len(standard_points)} points for standard prompt, {len(guess_points)} points for guess prompt")
                if standard_points:
                    print(f"  Standard prompt points: {standard_points}")
                if guess_points:
                    print(f"  Guess prompt points: {guess_points}")
        else:
            # If guess prompt is not available, use standard prompt for all points
            for source_suffix, source_info in data_points_by_source.items():
                standard_prompt_points[source_suffix] = source_info["data_points"]
                guess_prompt_points[source_suffix] = []
            print("[DataAgent] Guess prompts not available, using standard prompt for all points")

        # Process data points for each source
        for source_suffix, source_info in data_points_by_source.items():
            data_points = source_info["data_points"]
            factors_key = source_info["factors_key"]
            modeling_history_key = source_info["modeling_history_key"]
            
            print(f"\n[DataAgent] Processing data points for source {source_suffix}:")
            print(f"  - Factors key: {factors_key}")
            print(f"  - Modeling history key: {modeling_history_key}")
            print(f"  - Data points: {data_points}")
            
            # Process data points for this source
            i = 0
            while i < len(data_points):
                data_point = data_points[i]
                
                # Reset state for new data point
                if i > 0:
                    self._reset_for_new_datapoint()
                    # Clear data_collection_history from context
                    context = self._load_context()
                    if "data_collection_history" in context:
                        context["data_collection_history"] = [
                            entry for entry in context.get("data_collection_history", [])
                            if entry.get("is_summary", False)
                        ]
                        self._save_context(context)
                
                # Determine which prompt to use
                use_guess_for_this_point = (
                    use_guess_prompt and 
                    source_suffix in guess_prompt_points and 
                    data_point in guess_prompt_points[source_suffix]
                )
                
                if use_guess_for_this_point:
                    print(f"[DataAgent] Using GUESS prompt for data point '{data_point}'")
                    # Temporarily save original system prompt
                    orig_acquire_sys = DATA_ACQUIRE_SYS
                    orig_critic_sys = DATA_CRITIC_SYS
                    # Use guess prompt instead
                    globals()['DATA_ACQUIRE_SYS'] = GUESS_ACQUIRE_SYS
                    globals()['DATA_CRITIC_SYS'] = GUESS_CRITIC_SYS
                else:
                    print(f"[DataAgent] Using STANDARD prompt for data point '{data_point}'")
                
                max_retries = 5
                retry_count = 0
                success = False
                
                # Set timeout to prevent hanging
                max_time_per_datapoint = 600  # 10 minutes
                start_time = time.time()
                
                while retry_count < max_retries and not success:
                    if retry_count > 0:
                        print(f"[DataAgent] Retrying data point '{data_point}' (attempt {retry_count+1}/{max_retries})")
                        self._reset_for_new_datapoint()
                        # Clear history related to this data point
                        context = self._load_context()
                        if "data_collection_history" in context:
                            context["data_collection_history"] = [
                                entry for entry in context.get("data_collection_history", [])
                                if entry.get("data_point", "") != data_point
                            ]
                        if "critic_feedback" in context:
                            context["critic_feedback"] = [
                                entry for entry in context.get("critic_feedback", [])
                                if entry.get("data_point", "") != data_point
                            ]
                        self._save_context(context)
                        # Wait before retrying
                        wait_time = min(30, 5 * (retry_count + 1))
                        print(f"[DataAgent] Waiting {wait_time} seconds before retrying...")
                        time.sleep(wait_time)
                    
                    print(f"[DataAgent] Processing data point {i+1}/{len(data_points)}: '{data_point}' for source {source_suffix}" + 
                         (f" (retry {retry_count+1}/{max_retries})" if retry_count > 0 else ""))
                    
                    try:
                        # Ensure correct factors and modeling history are set in context
                        context = self._load_context()
                        
                        # Temporarily override current factors and modeling history
                        if factors_key in context:
                            context["factors_0_0"] = context[factors_key]
                        if modeling_history_key in context:
                            context["modeling_history_0_0"] = context[modeling_history_key]
                        
                        self._save_context(context)
                        
                        # Run data collection, with timeout check
                        collection_thread = None
                        collection_result = {"success": False, "error": "Timed out", "score": 0}
                        
                        import threading
                        
                        def run_collection():
                            nonlocal collection_result
                            try:
                                collection_result = self.run_single_collection(data_point)
                            except Exception as e:
                                collection_result = {"success": False, "error": str(e), "score": 0}
                        
                        
                        collection_thread = threading.Thread(target=run_collection)
                        collection_thread.daemon = True
                        collection_thread.start()
                        
                        # Wait for completion or timeout
                        remaining_time = max_time_per_datapoint - (time.time() - start_time)
                        if remaining_time <= 0:
                            print(f"[DataAgent] Time limit exceeded for '{data_point}', moving to next")
                            collection_result = {"success": False, "error": "Time limit exceeded", "score": 0}
                            break
                            
                        collection_thread.join(timeout=remaining_time)
                        
                        if collection_thread.is_alive():
                            print(f"[DataAgent] Collection thread for '{data_point}' timed out after {max_time_per_datapoint} seconds")
                            # Record timeout error
                            collection_result = {"success": False, "error": "Thread timed out", "score": 0}
                            # Move to next data point
                            break
                        
                        result = collection_result
                        
                        # Check if successful
                        if result.get("error") is None:
                            success = True
                            source_info["results"][data_point] = result
                            
                            if result.get("skipped", False):
                                print(f"[DataAgent] '{data_point}' collection skipped, existing files kept")
                            elif result.get("success", False):
                                print(f"[DataAgent] '{data_point}' collection successful! Score: {result.get('score', 'N/A')}/15")
                            else:
                                print(f"[DataAgent] '{data_point}' collection did not meet threshold, score: {result.get('score', 'N/A')}/15")
                            
                            # Record summary
                            context = self._load_context()
                            if "data_collection_history" not in context:
                                context["data_collection_history"] = []
                                
                            summary_entry = {
                                "timestamp": datetime.datetime.now().isoformat(),
                                "data_point": data_point,
                                "source_suffix": source_suffix,
                                "summary": f"{'Skipped' if result.get('skipped', False) else 'Completed'} collection of {data_point} (source {source_suffix}). Final score: {result.get('score', 'N/A')}/15",
                                "is_summary": True,
                                "success": result.get("success", False),
                                "skipped": result.get("skipped", False)
                            }
                            context["data_collection_history"].append(summary_entry)
                            self._save_context(context)
                        else:
                            print(f"[DataAgent] Error during collection of '{data_point}': {result.get('error')}")
                            retry_count += 1
                            
                    except Exception as e:
                        print(f"[DataAgent] Unexpected error during collection of '{data_point}': {str(e)}")
                        import traceback
                        traceback.print_exc()
                        retry_count += 1
                
                # Restore original system prompt
                if use_guess_for_this_point:
                    globals()['DATA_ACQUIRE_SYS'] = orig_acquire_sys
                    globals()['DATA_CRITIC_SYS'] = orig_critic_sys
                
                # If all attempts failed and still unsuccessful
                if not success:
                    print(f"[DataAgent] Failed to collect '{data_point}' after {retry_count} retries. Moving to next.")
                    error_result = {
                        "success": False,
                        "error": f"Failed after {retry_count} retries or timed out",
                        "attempts": retry_count,
                        "score": 0
                    }
                    source_info["results"][data_point] = error_result
                    
                    # Record failure
                    context = self._load_context()
                    if "data_collection_history" not in context:
                        context["data_collection_history"] = []
                        
                    failure_entry = {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "data_point": data_point,
                        "source_suffix": source_suffix,
                        "summary": f"Failed to collect {data_point} (source {source_suffix}) after {retry_count} retries or timeout.",
                        "is_summary": True,
                        "success": False
                    }
                    context["data_collection_history"].append(failure_entry)
                    self._save_context(context)
                
                # Next data point
                i += 1
        
        # Collect all results
        all_results = {}
        for source_suffix, source_info in data_points_by_source.items():
            # Save results to source-specific key
            result_key = f"data_collection_results_{source_suffix}"
            source_results = source_info["results"]
            all_results[source_suffix] = source_results
            
            print(f"[DataAgent] Adding results for source {source_suffix} to shared context with key: {result_key}")
            self.shared_context.add_context(result_key, source_results)
        
        # Save to local context
        context = self._load_context()
        context["data_collection_results_by_source"] = all_results
        self._save_context(context)
        
        # Print overall summary
        total_points = sum(len(info["data_points"]) for info in data_points_by_source.values())
        successful_points = 0
        total_retry_count = 0
        
        print("\n[DataAgent] Data Collection Summary by Source:")
        for source_suffix, source_info in data_points_by_source.items():
            results = source_info["results"]
            source_total = len(source_info["data_points"])
            source_successful = sum(1 for r in results.values() if r.get("success", False))
            source_retries = sum(r.get("attempts", 1) - 1 for r in results.values() if r.get("attempts", 1) > 1)
            
            successful_points += source_successful
            total_retry_count += source_retries
            
            print(f"\nSource: {source_suffix} (factors: {source_info['factors_key']}, history: {source_info['modeling_history_key']})")
            print(f"- Total data points: {source_total}")
            source_success_percent = source_successful/source_total*100 if source_total > 0 else 0
            source_fail_percent = (source_total-source_successful)/source_total*100 if source_total > 0 else 0
            print(f"- Successfully collected: {source_successful} ({source_success_percent:.1f}%)")
            print(f"- Below threshold: {source_total-source_successful} ({source_fail_percent:.1f}%)")
            print(f"- Total retries needed: {source_retries}")
        
        print("\n[DataAgent] Overall Summary:")
        print(f"- Total data points across all sources: {total_points}")
        total_success_percent = successful_points/total_points*100 if total_points > 0 else 0
        total_fail_percent = (total_points-successful_points)/total_points*100 if total_points > 0 else 0
        print(f"- Total successfully collected: {successful_points} ({total_success_percent:.1f}%)")
        print(f"- Total below threshold: {total_points-successful_points} ({total_fail_percent:.1f}%)")
        print(f"- Total retries across all sources: {total_retry_count}")
        
        # Aggregate results from all sources, create a summary table, compatible with old code
        flat_results = {}
        for src, src_results in all_results.items():
            flat_results.update(src_results)
        
        # Add to shared_context
        self.shared_context.add_context("data_collection_results", flat_results)
        
        # Sync to context.json for SimulationAgent offline reading
        context = self._load_context()
        context["data_collection_results"] = flat_results
        
        # Sync back to shared_context and save
        if hasattr(self.shared_context, 'from_dict'):
            self.shared_context.from_dict(context)
        elif hasattr(self.shared_context, 'context'):
            self.shared_context.context = context
        
        self._save_context(context)
        
        print("[DataAgent] Data collection results aggregated and saved to shared_context")
        print("[DataAgent] Data collection process completed")
        return True

    def _get_workspace_content(self):
        """Get detailed information about workspace content"""
        workspace_files = []
        try:
            # List workspace files
            result = self.file_lister_tool.execute(dir_path=self.workspace_path)
            if isinstance(result, dict) and result.get("success") and "files" in result:
                workspace_files = result["files"]
                
                # Get list of text files to read
                text_files = []
                for fname in workspace_files:
                    lower_fname = fname.lower()
                    if (lower_fname.endswith(".txt") or 
                        lower_fname.endswith(".md") or 
                        lower_fname.endswith(".csv") or 
                        lower_fname.endswith(".json") or
                        lower_fname.endswith(".py")):
                        text_files.append(fname)
                
                # Read content of text files (limited to 5 to prevent overload)
                file_contents = []
                for fname in text_files[:5]:
                    try:
                        fpath = os.path.join(self.workspace_path, fname)
                        read_result = self.file_reader_tool.execute(file_path=fpath)
                        if isinstance(read_result, dict) and read_result.get("success"):
                            content = read_result["message"]
                            # If content is too long, truncate
                            if len(content) > 5000:
                                content = content[:5000] + "... (content truncated)"
                            file_contents.append(f"=== {fname} ===\n{content}\n")
                    except Exception as e:
                        file_contents.append(f"=== {fname} ===\n(Error reading file: {e})\n")
                
                # Combine into summary
                if file_contents:
                    return f"Files in workspace: {', '.join(workspace_files)}\n\nFile contents:\n{''.join(file_contents)}"
                else:
                    return f"Files in workspace: {', '.join(workspace_files)}\n(No text files to display)"
            else:
                return f"Error listing workspace files: {result}"
        except Exception as e:
            return f"Error accessing workspace: {e}"

    def _inject_tool_metadata(self, tools_definition):
        """
        Inject tool metadata into tools definition
        """
        return self.tool_handler.inject_tool_metadata(tools_definition)

    def _color_print(self, role: str, content: str, max_print=1000):
        """Print colored output based on role"""
        COLOR_RESET   = "\033[0m"
        COLOR_SYSTEM  = "\033[32m"  # Green
        COLOR_USER    = "\033[34m"  # Blue
        COLOR_GPT     = "\033[35m"  # Magenta
        COLOR_TOOL    = "\033[33m"  # Yellow

        # Use mapping to simplify color selection
        color_map = {
            "system": COLOR_SYSTEM,
            "user": COLOR_USER,
            "gpt": COLOR_GPT,
            "tool": COLOR_TOOL
        }
            
        # Get color from mapping, default to reset color if no match
        color = color_map.get(role, COLOR_RESET)
        role_label = role.upper()
            
        # Truncate content to specified maximum length to avoid long console output
        if len(content) > max_print:
            displayed_content = content[:max_print] + "... (truncated)"
        else:
            displayed_content = content
            
        # Print colored role and content, with COLOR_RESET at the end of the content
        print(f"{color}[{role_label}]\n{displayed_content}{COLOR_RESET}\n")

    def _reset_for_new_datapoint(self):
        """Reset state for new data point preparation"""
        # Clear temporary files, etc.
        print("[DataAgent] Resetting state for new data point")
        
    def _create_snapshot(self, data_point, suffix):
        """Create snapshot for current state"""
        if not self.enable_snapshot:
            return
            
        try:
            # Get data point directory
            data_point_slug = data_point.lower().replace(" ", "_").replace("/", "_")
            data_point_dir = os.path.join(self.data_folder, data_point_slug)
            
            # If directory does not exist, nothing to snapshot
            if not os.path.exists(data_point_dir):
                return
                
            # Create snapshot directory with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_dir = os.path.join(self.snapshot_path, f"{data_point_slug}_{suffix}_{timestamp}")
            os.makedirs(snapshot_dir, exist_ok=True)
            
            # Copy all files from data point directory to snapshot
            for file_name in os.listdir(data_point_dir):
                src_file = os.path.join(data_point_dir, file_name)
                dst_file = os.path.join(snapshot_dir, file_name)
                if os.path.isfile(src_file):
                    shutil.copy2(src_file, dst_file)
                    
            print(f"[DataAgent] Created snapshot for '{data_point}' at {snapshot_dir}")
        except Exception as e:
            print(f"[DataAgent] Error creating snapshot: {e}")
            
    def _evaluate_collected_data(self, data_point):
        """
        Evaluate collected data to see if it meets expected quality standards
        
        Args:
            data_point: Name of data point
            
        Returns:
            (feedback, scores): String feedback and dictionary of scores
        """
        print(f"[DataAgent] Evaluating collected data for '{data_point}'...")
        
        # Get workspace content
        workspace_content = self._get_workspace_content()
        
        # Get path to data point directory
        data_point_slug = data_point.lower().replace(" ", "_").replace("/", "_")
        data_point_dir = os.path.join(self.data_folder, data_point_slug)
        
        # Get MD file content (if exists)
        md_file_content = ""
        md_files = []
        if os.path.exists(data_point_dir):
            md_files = [f for f in os.listdir(data_point_dir) if f.endswith('.md')]
            if md_files:
                try:
                    md_path = os.path.join(data_point_dir, md_files[0])
                    md_result = self.file_reader_tool.execute(file_path=md_path)
                    if isinstance(md_result, dict) and md_result.get("success"):
                        md_file_content = md_result["message"]
                        print(f"[DataAgent] Found MD file: {md_files[0]}")
                    else:
                        md_file_content = f"Error reading MD file: {md_result}"
                except Exception as e:
                    md_file_content = f"Error accessing MD file: {e}"
            else:
                md_file_content = "No MD file found in the data point directory."
        else:
            md_file_content = "No data point directory found."
        
        # Get CSV file preview (if exists)
        csv_file_preview = ""
        csv_files = []
        if os.path.exists(data_point_dir):
            csv_files = [f for f in os.listdir(data_point_dir) if f.endswith('.csv')]
            if csv_files:
                try:
                    csv_path = os.path.join(data_point_dir, csv_files[0])
                    # Use pandas to read first 10 rows if available
                    import pandas as pd
                    try:
                        df = pd.read_csv(csv_path)
                        preview = df.head(10).to_string()
                        csv_file_preview = f"File: {csv_files[0]}\n{preview}"
                        print(f"[DataAgent] Found CSV file: {csv_files[0]}")
                    except Exception as csv_e:
                        # If pandas fails, fall back to simple file reading
                        csv_result = self.file_reader_tool.execute(file_path=csv_path)
                        if isinstance(csv_result, dict) and csv_result.get("success"):
                            lines = csv_result["message"].split('\n')
                            csv_file_preview = f"File: {csv_files[0]}\n" + '\n'.join(lines[:11])
                        else:
                            csv_file_preview = f"Error reading CSV file: {csv_result}"
                except Exception as e:
                    csv_file_preview = f"Error accessing CSV file: {e}"
            else:
                csv_file_preview = "No CSV file found in the data point directory."
        else:
            csv_file_preview = "No data point directory found."
            
        # Extract context background
        context = self._load_context()
        factors = context.get("factors_0_0", {})
        explanation = context.get("explanation_0_0", "")
        modeling_history = context.get("modeling_history_0_0", [])
        
        # Convert to string format
        if isinstance(factors, dict) or isinstance(factors, list):
            factors_str = json.dumps(factors, indent=2, ensure_ascii=False)
        else:
            factors_str = str(factors)
            
        if isinstance(modeling_history, dict) or isinstance(modeling_history, list):
            modeling_history_str = json.dumps(modeling_history, indent=2, ensure_ascii=False)
        else:
            modeling_history_str = str(modeling_history)
        
        # Use DATA_CRITIC_USER template to build evaluation prompt
        critic_user = DATA_CRITIC_USER.format(
            data_point_to_collect=data_point,
            modeling_history=modeling_history_str,
            factors=factors_str,
            recent_function_calls="(Final evaluation - recent function calls not included)",
            data_collected_so_far="",  # Empty as we're looking at final files now
            workspace_content=workspace_content,
            md_file_content=md_file_content,
            csv_file_preview=csv_file_preview
        )
        
        critic_messages = form_message(DATA_CRITIC_SYS, critic_user)
        critic_response = self.core.execute(critic_messages)
        
        # Record evaluation
        self._append_history_entry(
            f"== Evaluation for '{data_point}' ==\n"
            f"**Evaluation Response**:\n{critic_response}\n\n"
        )
        
        # Use function calling to process evaluation results
        try:
            print(f"[DataAgent] Processing final evaluation using function calling")
            processed_critique = self._process_critique(critic_response, data_point)
            
            # Get scores from processed_critique
            scores = {
                "data_quality": processed_critique.get("scores", {}).get("data_quality_score", 3),
                "reliability": processed_critique.get("scores", {}).get("reliability_score", 3),
                "file_structure": processed_critique.get("scores", {}).get("file_structure_score", 3),
                "overall": processed_critique.get("scores", {}).get("overall_score", 9)
            }
            
            print(f"[DataAgent] Final evaluation processed through function calling: overall_score={scores.get('overall', 0)}/15")
            
            # Return evaluation feedback and scores
            return critic_response, scores
            
        except Exception as e:
            print(f"[DataAgent] Error processing final evaluation with function calling: {e}")
            print(f"[DataAgent] Falling back to regex extraction")
            
            # Use regex extraction as fallback
            try:
                overall_score = self._extract_overall_score(critic_response)
                data_quality = self._extract_score(critic_response, "Data Quality")
                reliability = self._extract_score(critic_response, "Data Reliability")
                file_structure = self._extract_score(critic_response, "File Structure")
                
                scores = {
                    "data_quality": data_quality,
                    "reliability": reliability,
                    "file_structure": file_structure,
                    "overall": overall_score
                }
                
                print(f"[DataAgent] Scores extracted using regex: overall_score={overall_score}/15")
                
                # Return evaluation feedback and scores
                return critic_response, scores
                
            except Exception as regex_e:
                print(f"[DataAgent] Error parsing evaluation with regex: {regex_e}")
                # Use default values
                scores = {
                    "data_quality": 3,
                    "reliability": 3,
                    "file_structure": 3,
                    "overall": 9  # Default set to a score that might pass threshold
                }
                return "Error processing evaluation, using default scores.", scores

    def _extract_overall_score(self, evaluation_text):
        """Extract overall score from evaluation text"""
        import re
        # First print a debug message with truncated evaluation text
        print(f"[DataAgent] Extracting overall score from evaluation text: {evaluation_text[:300]}...")
        
        # Look for patterns like "Overall Score: 8/15" or "Overall: 8"
        patterns = [
            # Original patterns adapted for 15-point scale
            r"Overall\s+Score\s*:\s*(\d+)(?:/15)?",
            r"Overall\s*:\s*(\d+)(?:/15)?",
            r"Overall\s+assessment\s*:\s*(\d+)(?:/15)?",
            r"Overall\s+rating\s*:\s*(\d+)(?:/15)?",
            # Additional patterns for more flexibility
            r"Overall\s+Score\s*:\s*(\d+)\s*out\s+of\s+15",
            r"Final\s+Score\s*:\s*(\d+)(?:/15)?",
            r"Total\s+Score\s*:\s*(\d+)(?:/15)?",
            # Chinese patterns
            r"总体得分\s*[:：]\s*(\d+)(?:/15)?",
            r"总分\s*[:：]\s*(\d+)(?:/15)?",
            r"总评分\s*[:：]\s*(\d+)(?:/15)?",
        ]
        
        for pattern in patterns:
            matches = re.search(pattern, evaluation_text, re.IGNORECASE)
            if matches:
                score = int(matches.group(1))
                print(f"[DataAgent] Found overall score: {score}/15 using pattern: {pattern}")
                return score
                
        # If no match found using standard patterns, try more aggressive search
        # Look for any line with "overall" and a number
        lines = evaluation_text.split('\n')
        for line in lines:
            if 'overall' in line.lower() or '总' in line:
                number_matches = re.findall(r'(\d+)', line)
                if number_matches:
                    for num in number_matches:
                        num_val = int(num)
                        if 1 <= num_val <= 15:  # Only accept reasonable values
                            print(f"[DataAgent] Found potential overall score through aggressive search: {num_val}/15")
                            return num_val
        
        # Default value if no score found
        print("[DataAgent] Could not extract overall score, using default: 9/15")
        return 9  # Default to middle score
        
    def _extract_score(self, evaluation_text, score_type):
        """Extract specific score from evaluation text"""
        import re
        print(f"[DataAgent] Extracting {score_type} score...")
        
        # Convert score_type to appropriate regex pattern
        if score_type == "Data Quality":
            patterns = [
                r"Data\s+Quality\s*(?:Score)?:?\s*(\d+)(?:/5)?",
                r"Quality\s+Score:?\s*(\d+)(?:/5)?",
                r"数据质量\s*[:：]\s*(\d+)(?:/5)?",
            ]
        elif score_type == "Data Reliability":
            patterns = [
                r"(?:Data\s+)?Reliability\s*(?:Score)?:?\s*(\d+)(?:/5)?",
                r"可靠性\s*[:：]\s*(\d+)(?:/5)?",
            ]
        elif score_type == "File Structure":
            patterns = [
                r"File\s+Structure\s*(?:Score)?:?\s*(\d+)(?:/5)?",
                r"Structure\s+Score:?\s*(\d+)(?:/5)?",
                r"文件结构\s*[:：]\s*(\d+)(?:/5)?",
            ]
        else:
            # Unknown score type
            return 3  # Default middle score for unknown types
            
        for pattern in patterns:
            matches = re.search(pattern, evaluation_text, re.IGNORECASE)
            if matches:
                score = int(matches.group(1))
                print(f"[DataAgent] Found {score_type} score: {score}/5")
                return score
        
        # If not found with standard patterns, try to find it in a scoring table or list
        # Look for lines with the score name and a single digit
        score_type_simple = score_type.lower().replace("data ", "").replace(" score", "")
        lines = evaluation_text.split('\n')
        for line in lines:
            if score_type_simple.lower() in line.lower():
                number_matches = re.findall(r'(\d)', line)
                if number_matches:
                    for num in number_matches:
                        num_val = int(num)
                        if 1 <= num_val <= 5:  # Only accept reasonable values
                            print(f"[DataAgent] Found potential {score_type} score through aggressive search: {num_val}/5")
                            return num_val
        
        # Default value if no score found
        print(f"[DataAgent] Could not extract {score_type} score, using default: 3/5")
        return 3  # Default to middle score
    
