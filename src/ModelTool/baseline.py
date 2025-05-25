import sys
import os
import json
import time
import yaml
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  
sys.path.append(BASE_DIR)

from src.tools.file_writer import File_Writer_Tool
from src.tools.file_reader import File_Reader_Tool
from src.tools.file_lister import File_Lister_Tool
from src.tools.web_download import Web_Download_Tool
from src.tools.web_search import Web_Search_Tool
from src.tools.url_text import URL_Text_Extractor_Tool
from src.tools.pdf_parsing import PDF_Parser_Tool
from src.tools.text_detector import Text_Detector_Tool
from src.tools.image_captioner import Image_Captioner_Tool
from src.tools.solution_generator import Solution_Generator_Tool
from src.tools.code_executor import Python_Execution_Tool

from src.ModelTool.utils.planner import BasePlanner
from src.ModelAgent.engines.core import Core

class BaseAgent:
    def __init__(self, config_path: str, workspace_path: str, max_iter=100):
        """Initialize BaseAgent with configuration and workspace path"""
        try:
            with open(config_path, "r", encoding="utf-8") as cf:
                config = yaml.safe_load(cf)
        except Exception as e:
            raise ValueError(f"Error reading config YAML from {config_path}: {e}")

        self.max_iter = max_iter
        self.model_name = config.get("model_name", "gpt-4o-mini")
        
        core_config = {
            "model": {
                "name": self.model_name,
                "temperature": config.get("temperature", 0),
            }
        }
        
        if "gpt" in self.model_name.lower():
            if config.get("aihubmix_api_key"):
                core_config["model"].update({
                    "type": "openai",
                    "openai_api_key": config.get("aihubmix_api_key"),
                    "openai_base_url": config.get("aihubmix_base_url")
                })
            else:
                core_config["model"].update({
                    "type": "openai",
                    "openai_api_key": config.get("openai_api_key")
                })

        else:
            core_config["model"].update({
                "type": "local",
                "port": config.get("port", 8000)
            })

        self.core = Core(core_config)
        print(f"[BaseAgent] Initialized Core with model_name={self.model_name}")

        # Initialize scratch board if enabled
        self.use_scratch_board = config.get("use_scratch_board", False)
        self.scratch_board = None
        print("[BaseAgent] ScratchBoard is DISABLED.")

        # Set up workspace and logging directories
        os.makedirs(workspace_path, exist_ok=True)
        self.run_folder = workspace_path
        os.environ["WORKSPACE_PATH"] = workspace_path
        print(f"[BaseAgent] WORKSPACE_PATH set to: {workspace_path}")

        # Initialize memory and history files
        self.memory_file = os.path.join(workspace_path, "memory.jsonl")
        self.history_file = os.path.join(workspace_path, "history.txt")
        
        for file_path in [self.memory_file, self.history_file]:
            if not os.path.exists(file_path):
                with open(file_path, "w", encoding="utf-8") as f:
                    if file_path == self.history_file:
                        f.write("=== LLM History Log ===\n")
                    else:
                        f.write("")

        # Initialize tools
        self.file_writer_tool = File_Writer_Tool()
        self.file_reader_tool = File_Reader_Tool()
        self.file_lister_tool = File_Lister_Tool()
        self.web_download_tool = Web_Download_Tool()
        self.web_search_tool = Web_Search_Tool()
        self.url_text_extractor_tool = URL_Text_Extractor_Tool()
        self.pdf_parser_tool = PDF_Parser_Tool()
        self.text_detector_tool = Text_Detector_Tool()
        self.image_captioner_tool = Image_Captioner_Tool()
        self.solution_generator_tool = Solution_Generator_Tool()
        self.python_execution_tool = Python_Execution_Tool()

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
            "solution_generator_tool": self.solution_generator_tool,
            "python_execution_tool": self.python_execution_tool,
        }
        
        # Initialize planner if enabled
        self.use_planner = config.get("use_planner", False)
        self.planner = None        
              
        if self.use_planner:
            self.planner = BasePlanner(config, main_agent=self)
            print("[BaseAgent] Planner is ENABLED.")
        else:
            print("[BaseAgent] Planner is DISABLED.")

    def _append_history_entry(self, text: str):
        with open(self.history_file, "a", encoding="utf-8") as hf:
            hf.write(text + "\n")

    def model_tool_call(self, messages, functions):
        """
        Call GPT and write conversation input/output to history.txt.
        """
        rounds = 0
        while True:
            rounds += 1
            try:
                # Extract system/user content
                system_content = ""
                user_content = ""
                for m in messages:
                    if m["role"] == "system":
                        system_content = m["content"]
                    elif m["role"] == "user":
                        user_content = m["content"]

                # Write log: Round X, system, user
                log_text = (
                    f"== [Round {rounds}] GPT Call ==\n"
                    f"**System**:\n{system_content}\n\n"
                    f"**User**:\n{user_content}\n\n"
                )
                self._append_history_entry(log_text)

                # Use Core's function_call_execute method
                response = self.core.function_call_execute(
                    messages=messages,
                    functions=functions,
                    max_length=300000
                )

                # Parse response
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
                elif hasattr(raw_msg, 'tool_calls') and raw_msg.tool_calls:
                    raw_msg_dict["function_call"] = {
                        "name": raw_msg.tool_calls[0].function.name,
                        "arguments": raw_msg.tool_calls[0].function.arguments
                    }

                response_str = json.dumps(raw_msg_dict, ensure_ascii=False, indent=2)
                log_text2 = f"**Raw Response**:\n{response_str}\n"
                self._append_history_entry(log_text2)

                print("================ Tool Call ==================")
                print(raw_msg_dict)
                print("================ Tool Call ==================")
                
                return raw_msg_dict["function_call"], raw_msg_dict["content"]

            except Exception as e:
                print(f"Chat Generation Error: {e}")
                time.sleep(5)
                if rounds > 3:
                    raise Exception("Chat Completion failed too many times")
                

    def handle_call(self, call_data: dict) -> dict:
        """
        Receive data conforming to multi_tools_executor schema (call_data),
        for each tool, determine use_tool, parse tool_params and call the corresponding execute().

        Returns a dictionary containing finish field (indicating whether to end) and execution results of each tool:
        {
            "finish": bool,
            "tool_results": {
                "file_writer_tool": "...",
                "file_reader_tool": "...",
                ...
            }
        }
        """

        results = {}
        tools_summary_list = []

        finish = call_data.get("finish", False)
        
        # ===== 0) Thinking Tool (Fake) =====
        think_conf = call_data.get("think", {})
        if think_conf.get("use_tool") == True or think_conf.get("use_tool") == "true":
            params = think_conf.get("tool_params", {})
            result = params["content"]
            results["think_tool"] = result
            tools_summary_list.append("Thinking Tool => thought about the problem")
        else:
            results["think_tool"] = None
        
        # ===== 1) File_Writer_Tool =====
        fw_conf = call_data.get("file_writer_tool", {})
        if fw_conf.get("use_tool") == True or fw_conf.get("use_tool") == 'true':
            params = fw_conf.get("tool_params", {})
            result = self.file_writer_tool.execute(
                file_path=params["file_path"],
                content=params["content"],
                mode=params["mode"]
            )
            results["file_writer_tool"] = result

            # If successful => write to scratch_board
            if isinstance(result, dict) and result.get("success") == True and self.use_scratch_board and self.scratch_board:
                self.scratch_board.record_tool_result("file_writer_tool", result["message"])

            # Assemble summary text
            truncated_content = params["content"][:300]
            if len(params["content"]) > 300:
                truncated_content += "..."
            summary_text = (
                f"File_Writer_Tool => wrote '{truncated_content}' to {params['file_path']} (mode={params['mode']})"
            )
            tools_summary_list.append(summary_text)
        else:
            results["file_writer_tool"] = None

        # ===== 2) File_Reader_Tool =====
        fr_conf = call_data.get("file_reader_tool", {})
        if fr_conf.get("use_tool") == True or fr_conf.get("use_tool") == 'true':
            params = fr_conf.get("tool_params", {})
            result = self.file_reader_tool.execute(file_path=params["file_path"])
            results["file_reader_tool"] = result

            if isinstance(result, dict) and result.get("success") == True and self.use_scratch_board and self.scratch_board:
                self.scratch_board.record_tool_result("file_reader_tool", result["message"])

            summary_text = f"File_Reader_Tool => read {params['file_path']}"
            tools_summary_list.append(summary_text)
        else:
            results["file_reader_tool"] = None

        # ===== 3) File_Lister_Tool =====
        fl_conf = call_data.get("file_lister_tool", {})
        if fl_conf.get("use_tool") == True or fl_conf.get("use_tool") == 'true':
            params = fl_conf.get("tool_params", {})
            result = self.file_lister_tool.execute(dir_path=params["dir_path"])
            results["file_lister_tool"] = result

            if isinstance(result, dict) and result.get("success") == True and self.use_scratch_board and self.scratch_board:
                self.scratch_board.record_tool_result("file_lister_tool", result["message"])

            summary_text = f"File_Lister_Tool => listed files under {params['dir_path']}"
            tools_summary_list.append(summary_text)
        else:
            results["file_lister_tool"] = None

        # ===== 4) Web_Download_Tool =====
        wd_conf = call_data.get("web_download_tool", {})
        if wd_conf.get("use_tool") == True or wd_conf.get("use_tool") == 'true':
            params = wd_conf.get("tool_params", {})
            result = self.web_download_tool.execute(url=params["url"], save_path=params["save_path"])
            results["web_download_tool"] = result

            if isinstance(result, dict) and result.get("success") == True and self.use_scratch_board and self.scratch_board:
                self.scratch_board.record_tool_result("web_download_tool", result["message"])

            summary_text = f"Web_Download_Tool => downloaded from {params['url']} to {params['save_path']}"
            tools_summary_list.append(summary_text)
        else:
            results["web_download_tool"] = None

        # ===== 5) Web_Search_Tool =====
        ws_conf = call_data.get("web_search_tool", {})
        if ws_conf.get("use_tool") == True or ws_conf.get("use_tool") == 'true':
            params = ws_conf.get("tool_params", {})
            result = self.web_search_tool.execute(
                query=params["query"],
                link=params["link"],
                num=params["num"]
            )
            results["web_search_tool"] = result

            if isinstance(result, dict) and result.get("success") == True and self.use_scratch_board and self.scratch_board:
                self.scratch_board.record_tool_result("web_search_tool", result["message"])

            summary_text = (
                f"Web_Search_Tool => searched '{params['query']}' (link={params['link']}, num={params['num']})"
            )
            tools_summary_list.append(summary_text)
        else:
            results["web_search_tool"] = None

        # ===== 6) URL_Text_Extractor_Tool =====
        ute_conf = call_data.get("url_text_extractor_tool", {})
        if ute_conf.get("use_tool") == True or ute_conf.get("use_tool") == 'true':
            params = ute_conf.get("tool_params", {})
            result = self.url_text_extractor_tool.execute(url=params["url"])
            results["url_text_extractor_tool"] = result

            if isinstance(result, dict) and result.get("success") == True and self.use_scratch_board and self.scratch_board:
                self.scratch_board.record_tool_result("url_text_extractor_tool", result["message"])

            summary_text = f"URL_Text_Extractor_Tool => extracted text from {params['url']}"
            tools_summary_list.append(summary_text)
        else:
            results["url_text_extractor_tool"] = None

        # ===== 7) PDF_Parser_Tool =====
        pdf_conf = call_data.get("pdf_parser_tool", {})
        if pdf_conf.get("use_tool") == True or pdf_conf.get("use_tool") == 'true':
            params = pdf_conf.get("tool_params", {})
            result = self.pdf_parser_tool.execute(
                pdf_path=params["pdf_path"],
                num_pages=params["num_pages"],
                min_size=params["min_size"]
            )
            results["pdf_parser_tool"] = result

            if isinstance(result, dict) and result.get("success") == True and self.use_scratch_board and self.scratch_board:
                self.scratch_board.record_tool_result("pdf_parser_tool", result["message"])

            summary_text = (
                f"PDF_Parser_Tool => parsed {params['pdf_path']} (pages={params['num_pages']}, min_size={params['min_size']})"
            )
            tools_summary_list.append(summary_text)
        else:
            results["pdf_parser_tool"] = None

        # ===== 8) Text_Detector_Tool =====
        td_conf = call_data.get("text_detector_tool", {})
        if td_conf.get("use_tool") == True or td_conf.get("use_tool") == 'true':
            params = td_conf.get("tool_params", {})
            result = self.text_detector_tool.execute(
                image=params["image"],
                languages=params["languages"],
                detail=params["detail"]
            )
            results["text_detector_tool"] = result

            if isinstance(result, dict) and result.get("success") == True and self.use_scratch_board and self.scratch_board:
                self.scratch_board.record_tool_result("text_detector_tool", result["message"])

            summary_text = (
                f"Text_Detector_Tool => performed OCR on {params['image']}, languages={params['languages']}"
            )
            tools_summary_list.append(summary_text)
        else:
            results["text_detector_tool"] = None

        # ===== 9) Image_Captioner_Tool =====
        ic_conf = call_data.get("image_captioner_tool", {})
        if ic_conf.get("use_tool") == True or ic_conf.get("use_tool") == 'true':
            params = ic_conf.get("tool_params", {})
            result = self.image_captioner_tool.execute(
                image=params["image"],
                prompt=params["prompt"]
            )
            results["image_captioner_tool"] = result

            if isinstance(result, dict) and result.get("success") == True and self.use_scratch_board and self.scratch_board:
                self.scratch_board.record_tool_result("image_captioner_tool", result["message"])

            short_prompt = params["prompt"][:20] + "..." if len(params["prompt"]) > 20 else params["prompt"]
            summary_text = f"Image_Captioner_Tool => captioned {params['image']} with prompt '{short_prompt}'"
            tools_summary_list.append(summary_text)
        else:
            results["image_captioner_tool"] = None

        # ===== 10) Solution_Generator_Tool =====
        sg_conf = call_data.get("solution_generator_tool", {})
        if sg_conf.get("use_tool") == True or sg_conf.get("use_tool") == 'true':
            params = sg_conf.get("tool_params", {})
            result = self.solution_generator_tool.execute(
                prompt=params["prompt"],
                image=params["image"]
            )
            results["solution_generator_tool"] = result

            if isinstance(result, dict) and result.get("success") == True and self.use_scratch_board and self.scratch_board:
                self.scratch_board.record_tool_result("solution_generator_tool", result["message"])

            snippet = params["prompt"][:20] + "..." if len(params["prompt"]) > 20 else params["prompt"]
            summary_text = f"Solution_Generator_Tool => LLM Q&A with prompt '{snippet}'"
            tools_summary_list.append(summary_text)
        else:
            results["solution_generator_tool"] = None

        # ===== 11) Python_Execution_Tool =====
        py_conf = call_data.get("python_execution_tool", {})
        if py_conf.get("use_tool") == True or py_conf.get("use_tool") == 'true':
            params = py_conf.get("tool_params", {})
            result = self.python_execution_tool.execute(
                file_path=params["file_path"],
                code_content=params["code_content"]
            )
            results["python_execution_tool"] = result

            if isinstance(result, dict) and result.get("success") == True and self.use_scratch_board and self.scratch_board:
                self.scratch_board.record_tool_result("python_execution_tool", result["message"])

            code_snippet = ""
            if params["code_content"]:
                code_snippet = params["code_content"][:300]
                if len(params["code_content"]) > 300:
                    code_snippet += "..."
            summary_text = f"Python_Execution_Tool => executed code snippet '{code_snippet}', file='{params['file_path']}'"
            tools_summary_list.append(summary_text)
        else:
            results["python_execution_tool"] = None

        # ===== End: Organize output_data, write to memory.jsonl =====
        output_data = {
            "finish": finish,
            "tool_results": results
        }

        next_index = self._get_next_memory_index()
        summary_str = " | ".join(tools_summary_list) if tools_summary_list else "No tool used."
        details_obj = {
            "call_data": call_data,
            "results": results
        }
        memory_entry = {
            "index": next_index,
            "summary": summary_str,
            "details": details_obj
        }
        self._append_memory_entry(memory_entry)

        return output_data

    def run(self, yaml_path=None):
        """
        Overall process:
        1) Read system, user, tools from YAML (only includes multi_tools_executor)
        2) For each multi_tools_executor.parameters.properties.*.description, inject detailed tool metadata
        3) Each loop:
            - Get recent tool call history from memory.jsonl
            - Read data_refined.json as "Here's the question you need to solve"
            - List workspace files + if .md/.py file then read content (truncate first 100000 chars)
            - Use user_prompt_template to construct user_msg
            - If use_planner=true, append planner.plan(...) result to user_msg
            - Call gpt_tool_call to get function call
            - handle_call to execute specific tool
        4) If finish=true, end loop
        """
        # (1) Read prompts.yaml
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                action_template = yaml.safe_load(f)
        except Exception as e:
            print(f"[BaseAgent] Error reading YAML: {e}")
            return

        system_prompt = action_template.get("system", "")
        user_prompt_template = action_template.get("user", "")
        tools_definition = action_template.get("tools", [])

        # (2) Append tool metadata to multi_tools_executor (same as previous logic)
        for tool_def in tools_definition:
            if tool_def.get("name") == "multi_tools_executor":
                parameters_def = tool_def.get("parameters", {})
                props = parameters_def.get("properties", {})
                for prop_key, prop_val in props.items():
                    if prop_key in self.tool_map:
                        tool_obj = self.tool_map[prop_key]
                        old_desc = prop_val.get("description", "")
                        meta_text = (
                            f"\n\n---\n"
                            f"**Tool Name**: {tool_obj.tool_name}\n"
                            f"**Version**: {tool_obj.tool_version}\n"
                            f"**Description**: {tool_obj.tool_description}\n"
                            f"**User Metadata**: {tool_obj.user_metadata}\n"
                        )
                        if tool_obj.demo_commands:
                            meta_text += "**Demo Commands**:\n"
                            for cmd_info in tool_obj.demo_commands:
                                cmd_cmd = cmd_info.get("command", "")
                                cmd_desc = cmd_info.get("description", "")
                                meta_text += f"  - `{cmd_cmd}` : {cmd_desc}\n"
                        if tool_obj.input_types:
                            meta_text += f"**Input Types**: {tool_obj.input_types}\n"
                        if tool_obj.output_type:
                            meta_text += f"**Output Type**: {tool_obj.output_type}\n"

                        new_desc = old_desc + meta_text
                        prop_val["description"] = new_desc

        round_count = 0
        last_tool_call_result = ""

        while True:
            round_count += 1

            # (a) Get recent 3 tool call history
            tool_call_history_str = self._build_tool_call_history(num=3)

            # (b) Read data_refined.json
            data_refined_path = os.path.join(os.environ["WORKSPACE_PATH"], "data_refined.json")
            if os.path.isfile(data_refined_path):
                try:
                    with open(data_refined_path, "r", encoding="utf-8") as f:
                        data_refined_content = f.read()
                except Exception as e:
                    data_refined_content = f"(Error reading data_refined.json: {e})"
            else:
                data_refined_content = "(No data_refined.json found in workspace)"

            # (c) List workspace files
            workspace_ls = self.file_lister_tool.execute(dir_path=os.environ["WORKSPACE_PATH"])
            if isinstance(workspace_ls, dict):
                workspace_ls_str = workspace_ls.get("message", "")
                # **Key change**: Read .md, .py files and combine into string
                expanded_file_contents = []
                if workspace_ls.get("success") and "files" in workspace_ls:
                    file_list = workspace_ls["files"]
                    for fname in file_list:
                        # If only want to read top-level files, can use fname directly
                        # If file_lister_tool recursively lists subdirectories, need to construct path here too
                        full_path = os.path.join(os.environ["WORKSPACE_PATH"], fname)
                        lower_fname = fname.lower()
                        if lower_fname.endswith(".md") or lower_fname.endswith(".py"):
                            read_result = self.file_reader_tool.execute(file_path=full_path)
                            if isinstance(read_result, dict) and read_result.get("success"):
                                file_content = read_result["message"]
                                truncated = file_content[:100000]  # Truncate first 100000 chars
                                expanded_file_contents.append(
                                    f"=== {fname} ===\n{truncated}\n=== END of {fname} ===\n"
                                )
                else:
                    file_list = []

                # Combine file list + possible file contents for Planner use
                workspace_detailed_str = (
                    f"List of files:\n{json.dumps(file_list, ensure_ascii=False, indent=2)}\n\n"
                    f"Below are .md/.py files with up to 100000 chars:\n"
                    + "\n".join(expanded_file_contents)
                )
            else:
                workspace_ls_str = str(workspace_ls)
                workspace_detailed_str = "(workspace listing not in expected format)"

            # (d) String replacement based on template
            user_msg = user_prompt_template
            user_msg = user_msg.replace("<<Tool call history>>", tool_call_history_str)
            user_msg = user_msg.replace("<<Last tool call result>>", last_tool_call_result)
            user_msg = user_msg.replace("<<query data>>", data_refined_content)
            user_msg = user_msg.replace("<<workspace -ls>>", workspace_ls_str)

            # If ScratchBoard enabled, also include it
            if self.use_scratch_board and self.scratch_board:
                scratch_text = self.scratch_board.export_as_text()
                user_msg += "\n\n**Scratch Board**:\n" + scratch_text

            # (e) If Planner enabled, first construct a more detailed status_text and call planner.plan()
            if self.use_planner and self.planner:
                status_text = (
                    f"Recent tool calls:\n{tool_call_history_str}\n\n"
                    f"Data refined content:\n{data_refined_content}\n\n"
                    f"Workspace listing summary:\n{workspace_ls_str}\n\n"
                    f"Last tool call result: {last_tool_call_result}\n\n"
                    # **Key change**: Also pass .md/.py file contents
                    f"(Detailed file contents for .md/.py below)\n\n{workspace_detailed_str}\n"
                )
                plan_result = self.planner.plan(status_text)
                user_msg += (
                    "\n\nHere's the planner's command about what you should do. "
                    "Follow the command, and do the first thing in the todo list.:\n"
                    + plan_result
                )

            # Print to terminal (optional)
            self._color_print("system", system_prompt)
            self._color_print("user",   user_msg)

            # (f) Call the Model
            try:
                function_call, content = self.model_tool_call(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_msg},
                    ],
                    functions=tools_definition
                )
            except Exception as e:
                print(f"[BaseAgent] GPT tool call error: {e}")
                break

            
            if not function_call:
                print("[BaseAgent] No function calls returned. Record the thinking ...")
                # break
                function_call = {"name": "multi_tools_executor", "arguments": {"think": {"use_tool": True, "tool_params": {"content": content}}}}
            
            function_name_str = function_call.get("name", "")
            function_args_str = function_call.get("arguments", "")
            
            # If function_name_str is multi_tools_executor, need special handling
            if function_name_str == "multi_tools_executor":
                try:
                    tool_call_dict = json.loads(function_args_str) if type(function_args_str) == str else function_args_str
                except json.JSONDecodeError as e:
                    print(f"[BaseAgent] JSON decode error: {e}")
                    break
            else:
                parsed_function = json.loads(function_args_str) if type(function_args_str) == str else function_args_str
                if "use_tool" in parsed_function and "tool_params" in parsed_function:
                    tool_call_dict = {function_name_str.lower(): parsed_function}
                else:
                    tool_call_dict = {function_name_str.lower(): {"use_tool": True, "tool_params": parsed_function}}
            
            # Call handle_call to execute tool
            handle_res = self.handle_call(tool_call_dict)
            last_tool_call_result = json.dumps(handle_res["tool_results"], ensure_ascii=False)
            self._color_print("system", json.dumps(handle_res, ensure_ascii=False))

            if handle_res["finish"] == True or handle_res["finish"] == 'true':
                print("[BaseAgent] Model indicated finish==True. Stopping loop.")
                break

            if round_count > self.max_iter:
                print(f"[BaseAgent] Exceeded {self.max_iter} rounds, stopping.")
                break

        print("[BaseAgent] run finished.")

    def _build_tool_call_history(self, num = 10) -> str:
        """
        Read all records from memory.jsonl:
        - For earliest (N - 3) entries, only return summary.
        - For recent 3 entries, return more complete information (including details).
        If total entries <= 3, return detailed content for all.
        """

        if not os.path.isfile(self.memory_file):
            return "(No history)"

        lines = []
        with open(self.memory_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(line)

        if not lines:
            return "(No history)"

        total_count = len(lines)
        if total_count <= num:
            older_part = []
            recent_part = lines
        else:
            older_part = lines[:-num]
            recent_part = lines[-num:]

        text_segments = []

        # For older_part only show summary
        for ln in older_part:
            try:
                obj = json.loads(ln)
                index = obj.get("index", -1)
                summary = obj.get("summary", "")
                text_segments.append(f"(Older) Index {index} => [Summary]: {summary}")
            except:
                pass

        # For recent_part show more complete information
        for ln in recent_part:
            try:
                obj = json.loads(ln)
                index = obj.get("index", -1)
                summary = obj.get("summary", "")
                details_obj = obj.get("details", {})
                text_segments.append(
                    f"(Recent) Index {index} => [Summary]: {summary}\n"
                    f"     [Details]: {json.dumps(details_obj, ensure_ascii=False)}"
                )
            except:
                pass

        return "\n".join(text_segments)

    def _get_next_memory_index(self) -> int:
        """
        Read self.memory_file (jsonl), calculate next index.
        If file doesn't exist or is empty, start from 0.
        """
        if not os.path.isfile(self.memory_file):
            return 0

        count = 0
        with open(self.memory_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    count += 1
        return count

    def _append_memory_entry(self, entry: dict):
        """
        Append a record to the end of memory.jsonl file (in json line format).
        """
        with open(self.memory_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False))
            f.write("\n")

    def _color_print(self, role: str, content: str, max_print=10000):
        """
        Print with different colors based on role, and limit to max 10000 chars.
        role can be: 'system', 'user', 'gpt'
        """
        COLOR_RESET   = "\033[0m"
        COLOR_SYSTEM  = "\033[32m"  # Green
        COLOR_USER    = "\033[34m"  # Blue
        COLOR_GPT     = "\033[35m"  # Magenta

        if role == "system":
            color = COLOR_SYSTEM
            role_label = "SYSTEM"
        elif role == "user":
            color = COLOR_USER
            role_label = "USER"
        elif role == "gpt":
            color = COLOR_GPT
            role_label = "GPT"
        else:
            color = COLOR_RESET
            role_label = role.upper()

        truncated = content[:max_print]
        if len(content) > max_print:
            truncated += "\n... (content truncated) ..."

        print(f"{color}[{role_label}] {truncated}{COLOR_RESET}\n")

def process_single_problem(gold_id: str, problem_data: Dict[str, Any], config_path: str, base_output_dir: str, yaml_path: str = None) -> None:
    """Process a single problem using BaseAgent"""
    # try:
    if True:
        workspace_path = os.path.join(base_output_dir, gold_id)
        
        if os.path.exists(workspace_path) and os.path.exists(os.path.join(workspace_path, "final_report.md")):
            print(f"!!!! Skipping {gold_id} because it already exists !!!!")
            return
        if os.path.exists(workspace_path) and len(open(os.path.join(workspace_path, "memory.jsonl")).readlines()) >= 20:
            print("Memory Length > 20, prioritize others ...")
            return
            
        os.makedirs(workspace_path, exist_ok=True)

        # Save problem data
        data_refined_path = os.path.join(workspace_path, "data_refined.json")
        problem = problem_data['question']
        decomposition = problem_data['decomposition']
        raw_question_data = {
            "modeling problem": problem,
            "decomposed requirements": decomposition
        }
        with open(data_refined_path, "w", encoding="utf-8") as f:
            json.dump(raw_question_data, f, indent=2)

        # Initialize and run agent
        agent = BaseAgent(config_path, workspace_path, max_iter=25)
        agent.run(yaml_path=yaml_path)
        

    # except Exception as e:
    #     print(f"Error processing problem {gold_id}: {e}")

def process_problems_parallel(problems_file: str, config_path: str, base_output_dir: str, max_workers: int = 4, yaml_path: str = None):
    """Process multiple problems in parallel"""
    try:
        # Load problems from JSON file
        with open(problems_file, "r", encoding="utf-8") as f:
            problems = json.load(f)

        # Create base output directory
        os.makedirs(base_output_dir, exist_ok=True)

        # Process problems in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for gold_id, problem in problems.items():
                future = executor.submit(process_single_problem, gold_id, problem, config_path, base_output_dir, yaml_path)
                futures.append(future)

            # Wait for all tasks to complete
            for future in futures:
                future.result()

    except Exception as e:
        print(f"Error in parallel processing: {e}")


if __name__ == "__main__":
    # Configuration
    problems_file = "../data/modeling_data_final.json"  # JSON file containing problems
    config_path = "./model_config.yaml"  # Model configuration file
    base_output_dir = "../output_workspace_modeltool"  # Base directory for all outputs
    yaml_path = "../baseprompts.yaml"
    max_workers = 5 # Number of parallel threads
    
    model_name = yaml.safe_load(open(config_path, "r", encoding="utf-8"))["model_name"]
    print(f"Model name: {model_name}")
    base_output_dir = os.path.join(base_output_dir, model_name)
    if not os.path.exists(base_output_dir):
        os.makedirs(base_output_dir)
    
    # Run parallel processing
    process_problems_parallel(problems_file, config_path, base_output_dir, max_workers, yaml_path=yaml_path)
