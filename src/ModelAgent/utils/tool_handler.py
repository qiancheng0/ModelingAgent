import os
import json
from copy import deepcopy

# Import tools for data collection
from src.tools.file_writer import File_Writer_Tool
from src.tools.file_reader import File_Reader_Tool
from src.tools.file_lister import File_Lister_Tool
from src.tools.web_download import Web_Download_Tool
from src.tools.web_search import Web_Search_Tool
from src.tools.url_text import URL_Text_Extractor_Tool
from src.tools.pdf_parsing import PDF_Parser_Tool
from src.tools.text_detector import Text_Detector_Tool
from src.tools.image_captioner import Image_Captioner_Tool
from src.tools.file_extractor import File_Extractor_Tool
from src.tools.code_executor import Python_Execution_Tool
from src.tools.file_editor import File_Edit_Tool

class ToolHandler:
    """
    Class for handling tool initialization, execution and metadata injection.
    Used by DataAgent to manage all tool-related operations.
    """
    def __init__(self, config):
        """
        Initialize all tools based on configuration
        
        Args:
            config: Dictionary containing configuration settings
        """
        self.config = config
        
        # Initialize tools with error handling
        self.file_writer_tool = File_Writer_Tool()
        self.file_reader_tool = File_Reader_Tool()
        self.file_lister_tool = File_Lister_Tool()
        
        try:
            self.file_editor_tool = File_Edit_Tool()
            print("[ToolHandler] File_Edit_Tool initialized")
        except Exception as e:
            print(f"[ToolHandler] Warning: Failed to initialize File_Edit_Tool: {e}")
            self.file_editor_tool = None
        
        # Try to initialize file extractor tool
        try:
            self.file_extractor_tool = File_Extractor_Tool()
        except Exception as e:
            print(f"[ToolHandler] Warning: Failed to initialize File_Extractor_Tool: {e}")
            self.file_extractor_tool = None
        
        try:
            self.python_execution_tool = Python_Execution_Tool()
            print("[ToolHandler] Python_Execution_Tool initialized")
        except Exception as e:
            print(f"[ToolHandler] Warning: Failed to initialize Python_Execution_Tool: {e}")
            self.python_execution_tool = None
        
        # Set up Serper API key (for web_search_tool)
        serper_api_key = self.config.get("serper_api_key") or self.config.get("model", {}).get("serper_api_key")
        if serper_api_key:
            # Temporarily set environment variable
            os.environ["SERPER_API_KEY"] = serper_api_key
            print(f"[ToolHandler] Using Serper API key from config")
            
        try:
            self.web_download_tool = Web_Download_Tool()
        except Exception as e:
            print(f"[ToolHandler] Warning: Failed to initialize Web_Download_Tool: {e}")
            self.web_download_tool = None
            
        try:
            self.web_search_tool = Web_Search_Tool()
            if serper_api_key:
                print("[ToolHandler] Web_Search_Tool initialized with Serper API key from config")
        except Exception as e:
            print(f"[ToolHandler] Warning: Failed to initialize Web_Search_Tool: {e}")
            self.web_search_tool = None
            
        try:
            self.url_text_extractor_tool = URL_Text_Extractor_Tool()
        except Exception as e:
            print(f"[ToolHandler] Warning: Failed to initialize URL_Text_Extractor_Tool: {e}")
            self.url_text_extractor_tool = None
            
        try:
            self.pdf_parser_tool = PDF_Parser_Tool()
        except Exception as e:
            print(f"[ToolHandler] Warning: Failed to initialize PDF_Parser_Tool: {e}")
            self.pdf_parser_tool = None
            
        try:
            self.text_detector_tool = Text_Detector_Tool()
        except Exception as e:
            print(f"[ToolHandler] Warning: Failed to initialize Text_Detector_Tool: {e}")
            self.text_detector_tool = None

        # Extract OpenAI API key from config, it's located under model.api_key path
        model_config = self.config.get("model", {})
        openai_api_key = model_config.get("api_key", os.environ.get("OPENAI_API_KEY"))
        
        if openai_api_key:
            # Temporary set environment variable for tool initialization
            os.environ["OPENAI_API_KEY"] = openai_api_key
            try:
                self.image_captioner_tool = Image_Captioner_Tool()
                print("[ToolHandler] Image_Captioner_Tool initialized with API key from config")
            except Exception as e:
                print(f"[ToolHandler] Warning: Failed to initialize Image_Captioner_Tool: {e}")
                self.image_captioner_tool = None
        else:
            print("\n[ToolHandler] Note: To enable OpenAI-related tools, set the OPENAI_API_KEY environment variable or add API key in config:")
            print("  export OPENAI_API_KEY=your_api_key_here")
            print("  or configure in config file: model.api_key")
            self.image_captioner_tool = None
            
        print("[ToolHandler] Tools initialization completed.")

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
            "python_execution_tool": self.python_execution_tool,
            "file_editor_tool": self.file_editor_tool,
        }
    
    def handle_call(self, call_data: dict, data_point=None, context_path=None):
        """
        Receive tool call data, execute appropriate tools, and return the results
        
        Args:
            call_data: Dictionary containing tool call data
            data_point: Optional data point being processed (for history tracking)
            context_path: Path to context.json file for logging history
        
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
        results = {}
        tools_summary_list = []

        # Security check: Ensure call_data is a dictionary type
        if not isinstance(call_data, dict):
            print(f"[ToolHandler] Warning: Received invalid call_data type: {type(call_data)}")
            return {
                "finish": False,
                "tool_results": {"error": f"Invalid call_data type: {type(call_data)}"}
            }

        finish = call_data.get("finish", False)

        # ===== 1) File_Writer_Tool =====
        fw_conf = call_data.get("file_writer_tool")
        if fw_conf is not None and fw_conf.get("use_tool"):
            if self.file_writer_tool is None:
                results["file_writer_tool"] = {"success": False, "message": "File_Writer_Tool is not available"}
                tools_summary_list.append("File_Writer_Tool => Not available")
            else:
                params = fw_conf.get("tool_params", {})
                if not params.get("file_path"):
                    error_msg = "Missing required parameter: 'file_path'"
                    results["file_writer_tool"] = {"success": False, "message": error_msg}
                    tools_summary_list.append(f"File_Writer_Tool => {error_msg} | Received: {json.dumps(params)}")
                elif "content" not in params:
                    error_msg = "Missing required parameter: 'content'"
                    results["file_writer_tool"] = {"success": False, "message": error_msg}
                    tools_summary_list.append(f"File_Writer_Tool => {error_msg} | Received: {json.dumps(params)}")
                else:
                    result = self.file_writer_tool.execute(
                        file_path=params["file_path"],
                        content=params["content"],
                        mode=params.get("mode", "w")
                    )
                    results["file_writer_tool"] = result

                    # Create summary text
                    truncated_content = params["content"][:300]
                    if len(params["content"]) > 300:
                        truncated_content += "..."
                    summary_text = (
                        f"File_Writer_Tool => wrote '{truncated_content}' to {params['file_path']} (mode={params.get('mode', 'w')})"
                    )
                    tools_summary_list.append(summary_text)
        else:
            results["file_writer_tool"] = None

        # ===== 2) File_Reader_Tool =====
        fr_conf = call_data.get("file_reader_tool")
        if fr_conf is not None and fr_conf.get("use_tool"):
            if self.file_reader_tool is None:
                results["file_reader_tool"] = {"success": False, "message": "File_Reader_Tool is not available"}
                tools_summary_list.append("File_Reader_Tool => Not available")
            else:
                params = fr_conf.get("tool_params", {})
                if not params.get("file_path"):
                    error_msg = "Missing required parameter: 'file_path'"
                    results["file_reader_tool"] = {"success": False, "message": error_msg}
                    tools_summary_list.append(f"File_Reader_Tool => {error_msg} | Received: {json.dumps(params)}")
                else:
                    result = self.file_reader_tool.execute(file_path=params["file_path"])
                    results["file_reader_tool"] = result

                    summary_text = f"File_Reader_Tool => read {params['file_path']}"
                    tools_summary_list.append(summary_text)
        else:
            results["file_reader_tool"] = None

        # ===== 3) File_Lister_Tool =====
        fl_conf = call_data.get("file_lister_tool")
        if fl_conf is not None and fl_conf.get("use_tool"):
            if self.file_lister_tool is None:
                results["file_lister_tool"] = {"success": False, "message": "File_Lister_Tool is not available"}
                tools_summary_list.append("File_Lister_Tool => Not available")
            else:
                params = fl_conf.get("tool_params", {})
                if not params.get("dir_path"):
                    error_msg = "Missing required parameter: 'dir_path'"
                    results["file_lister_tool"] = {"success": False, "message": error_msg}
                    tools_summary_list.append(f"File_Lister_Tool => {error_msg} | Received: {json.dumps(params)}")
                else:
                    result = self.file_lister_tool.execute(dir_path=params["dir_path"])
                    results["file_lister_tool"] = result

                    summary_text = f"File_Lister_Tool => listed files under {params['dir_path']}"
                    tools_summary_list.append(summary_text)
        else:
            results["file_lister_tool"] = None

        # ===== 4) Web_Download_Tool =====
        wd_conf = call_data.get("web_download_tool")
        if wd_conf is not None and wd_conf.get("use_tool"):
            if self.web_download_tool is None:
                results["web_download_tool"] = {"success": False, "message": "Web_Download_Tool is not available"}
                tools_summary_list.append("Web_Download_Tool => Not available")
            else:
                params = wd_conf.get("tool_params", {})
                missing_params = []
                if not params.get("url"):
                    missing_params.append("url")
                if not params.get("save_path"):
                    missing_params.append("save_path")
                
                if missing_params:
                    error_msg = f"Missing required parameters: {', '.join(missing_params)}"
                    results["web_download_tool"] = {"success": False, "message": error_msg}
                    tools_summary_list.append(f"Web_Download_Tool => {error_msg} | Received: {json.dumps(params)}")
                else:
                    result = self.web_download_tool.execute(url=params["url"], save_path=params["save_path"])
                    results["web_download_tool"] = result

                    summary_text = f"Web_Download_Tool => downloaded from {params['url']} to {params['save_path']}"
                    tools_summary_list.append(summary_text)
        else:
            results["web_download_tool"] = None

        # ===== 5) Web_Search_Tool =====
        ws_conf = call_data.get("web_search_tool")
        if ws_conf is not None and ws_conf.get("use_tool"):
            if self.web_search_tool is None:
                results["web_search_tool"] = {"success": False, "message": "Web_Search_Tool is not available"}
                tools_summary_list.append("Web_Search_Tool => Not available")
            else:
                params = ws_conf.get("tool_params", {})
                if not params.get("query"):
                    error_msg = "Missing required parameter: 'query'"
                    results["web_search_tool"] = {"success": False, "message": error_msg}
                    tools_summary_list.append(f"Web_Search_Tool => {error_msg} | Received: {json.dumps(params)}")
                else:
                    link = params.get("link", True)
                    num = params.get("num", 5)
                    result = self.web_search_tool.execute(
                        query=params["query"],
                        link=link,
                        num=num
                    )
                    results["web_search_tool"] = result

                    summary_text = (
                        f"Web_Search_Tool => searched '{params['query']}' (link={link}, num={num})"
                    )
                    tools_summary_list.append(summary_text)
        else:
            results["web_search_tool"] = None

        # ===== 6) URL_Text_Extractor_Tool =====
        ute_conf = call_data.get("url_text_extractor_tool")
        if ute_conf is not None and ute_conf.get("use_tool"):
            if self.url_text_extractor_tool is None:
                results["url_text_extractor_tool"] = {"success": False, "message": "URL_Text_Extractor_Tool is not available"}
                tools_summary_list.append("URL_Text_Extractor_Tool => Not available")
            else:
                params = ute_conf.get("tool_params", {})
                if not params.get("url"):
                    error_msg = "Missing required parameter: 'url'"
                    results["url_text_extractor_tool"] = {"success": False, "message": error_msg}
                    tools_summary_list.append(f"URL_Text_Extractor_Tool => {error_msg} | Received: {json.dumps(params)}")
                else:
                    result = self.url_text_extractor_tool.execute(url=params["url"])
                    results["url_text_extractor_tool"] = result

                    summary_text = f"URL_Text_Extractor_Tool => extracted text from {params['url']}"
                    tools_summary_list.append(summary_text)
        else:
            results["url_text_extractor_tool"] = None

        # ===== 7) PDF_Parser_Tool =====
        pdf_conf = call_data.get("pdf_parser_tool")
        if pdf_conf is not None and pdf_conf.get("use_tool"):
            if self.pdf_parser_tool is None:
                results["pdf_parser_tool"] = {"success": False, "message": "PDF_Parser_Tool is not available"}
                tools_summary_list.append("PDF_Parser_Tool => Not available")
            else:
                params = pdf_conf.get("tool_params", {})
                if not params.get("pdf_path"):
                    error_msg = "Missing required parameter: 'pdf_path'"
                    results["pdf_parser_tool"] = {"success": False, "message": error_msg}
                    tools_summary_list.append(f"PDF_Parser_Tool => {error_msg} | Received: {json.dumps(params)}")
                else:
                    num_pages = params.get("num_pages", "all")
                    min_size = params.get("min_size", 300)
                    result = self.pdf_parser_tool.execute(
                        pdf_path=params["pdf_path"],
                        num_pages=num_pages,
                        min_size=min_size
                    )
                    results["pdf_parser_tool"] = result

                    summary_text = (
                        f"PDF_Parser_Tool => parsed {params['pdf_path']} (pages={num_pages}, min_size={min_size})"
                    )
                    tools_summary_list.append(summary_text)
        else:
            results["pdf_parser_tool"] = None

        # ===== 8) Text_Detector_Tool =====
        td_conf = call_data.get("text_detector_tool")
        if td_conf is not None and td_conf.get("use_tool"):
            if self.text_detector_tool is None:
                results["text_detector_tool"] = {"success": False, "message": "Text_Detector_Tool is not available"}
                tools_summary_list.append("Text_Detector_Tool => Not available")
            else:
                params = td_conf.get("tool_params", {})

                if not params.get("image"):
                    error_msg = "Missing required parameter: 'image'"
                    results["text_detector_tool"] = {"success": False, "message": error_msg}
                    tools_summary_list.append(f"Text_Detector_Tool => {error_msg} | Received: {json.dumps(params)}")
                else:
                    languages = params.get("languages", ["en"])
                    detail = params.get("detail", "low")
                    result = self.text_detector_tool.execute(
                        image=params["image"],
                        languages=languages,
                        detail=detail
                    )
                    results["text_detector_tool"] = result

                    summary_text = (
                        f"Text_Detector_Tool => performed OCR on {params['image']}, languages={languages}"
                    )
                    tools_summary_list.append(summary_text)
        else:
            results["text_detector_tool"] = None

        # ===== 9) File_Extractor_Tool =====
        fe_conf = call_data.get("file_extractor_tool")
        if fe_conf is not None and fe_conf.get("use_tool"):
            if self.file_extractor_tool is None:
                results["file_extractor_tool"] = {"success": False, "message": "File_Extractor_Tool is not available"}
                tools_summary_list.append("File_Extractor_Tool => Not available")
            else:
                params = fe_conf.get("tool_params", {})
                if not params.get("archive_path"):
                    error_msg = "Missing required parameter: 'archive_path'"
                    results["file_extractor_tool"] = {"success": False, "message": error_msg}
                    tools_summary_list.append(f"File_Extractor_Tool => {error_msg} | Received: {json.dumps(params)}")
                else:
                    # Handle optional parameters
                    extract_dir = params.get("extract_dir")
                    password = params.get("password")
                    
                    # Execute with available parameters
                    if extract_dir and password:
                        result = self.file_extractor_tool.execute(
                            archive_path=params["archive_path"],
                            extract_dir=extract_dir,
                            password=password
                        )
                    elif extract_dir:
                        result = self.file_extractor_tool.execute(
                            archive_path=params["archive_path"],
                            extract_dir=extract_dir
                        )
                    elif password:
                        result = self.file_extractor_tool.execute(
                            archive_path=params["archive_path"],
                            password=password
                        )
                    else:
                        result = self.file_extractor_tool.execute(
                            archive_path=params["archive_path"]
                        )
                    
                    results["file_extractor_tool"] = result

                    # Create summary text
                    extract_dir_str = f" to {extract_dir}" if extract_dir else ""
                    password_str = " with password" if password else ""
                    summary_text = f"File_Extractor_Tool => extracted {params['archive_path']}{extract_dir_str}{password_str}"
                    tools_summary_list.append(summary_text)
        else:
            results["file_extractor_tool"] = None

        # ===== 10) Image_Captioner_Tool =====
        ic_conf = call_data.get("image_captioner_tool")
        if ic_conf is not None and ic_conf.get("use_tool"):
            if self.image_captioner_tool is None:
                results["image_captioner_tool"] = {"success": False, "message": "Image_Captioner_Tool is not available"}
                tools_summary_list.append("Image_Captioner_Tool => Not available (OPENAI_API_KEY not set)")
            else:
                params = ic_conf.get("tool_params", {})
                missing_params = []
                if not params.get("image"):
                    missing_params.append("image")
                if not params.get("prompt"):
                    missing_params.append("prompt")
                
                if missing_params:
                    error_msg = f"Missing required parameters: {', '.join(missing_params)}"
                    results["image_captioner_tool"] = {"success": False, "message": error_msg}
                    tools_summary_list.append(f"Image_Captioner_Tool => {error_msg} | Received: {json.dumps(params)}")
                else:
                    result = self.image_captioner_tool.execute(
                        image=params["image"],
                        prompt=params["prompt"]
                    )
                    results["image_captioner_tool"] = result

                    short_prompt = params["prompt"][:20] + "..." if len(params["prompt"]) > 20 else params["prompt"]
                    summary_text = f"Image_Captioner_Tool => captioned {params['image']} with prompt '{short_prompt}'"
                    tools_summary_list.append(summary_text)
        else:
            results["image_captioner_tool"] = None
            
        # ===== 11) Python_Execution_Tool =====
        py_conf = call_data.get("python_execution_tool")
        if py_conf is not None and py_conf.get("use_tool"):
            if self.python_execution_tool is None:
                results["python_execution_tool"] = {"success": False, "message": "Python_Execution_Tool is not available"}
                tools_summary_list.append("Python_Execution_Tool => Not available")
            else:
                params = py_conf.get("tool_params", {})
                
                file_path = params.get("file_path")
                code_content = params.get("code_content")
                
                if not file_path and not code_content:
                    error_msg = "Error: Either file_path or code_content must be provided."
                    results["python_execution_tool"] = {"success": False, "message": error_msg}
                    tools_summary_list.append(f"Python_Execution_Tool => {error_msg} | Received: {json.dumps(params)}")
                else:
                    if file_path and code_content:
                        result = self.python_execution_tool.execute(
                            file_path=file_path,
                            code_content=code_content
                        )
                    elif file_path:
                        result = self.python_execution_tool.execute(
                            file_path=file_path
                        )
                    else:  # code_content
                        result = self.python_execution_tool.execute(
                            code_content=code_content
                        )
                    
                    results["python_execution_tool"] = result
                    
                    execution_source = f"file {file_path}" if file_path else "inline code"
                    if code_content and len(code_content) > 50:
                        code_preview = code_content[:50] + "..."
                    else:
                        code_preview = code_content if code_content else ""
                    
                    summary_text = f"Python_Execution_Tool => executed {execution_source}"
                    if code_preview:
                        summary_text += f" with content preview: '{code_preview}'"
                    
                    tools_summary_list.append(summary_text)
        else:
            results["python_execution_tool"] = None

        # ===== 12) File_Editor_Tool =====
        fe_conf = call_data.get("file_editor_tool")
        if fe_conf is not None and fe_conf.get("use_tool"):
            if self.file_editor_tool is None:
                results["file_editor_tool"] = {"success": False, "message": "File_Editor_Tool is not available"}
                tools_summary_list.append("File_Editor_Tool => Not available")
            else:
                params = fe_conf.get("tool_params", {})
                
                missing_params = []
                if not params.get("file_path"):
                    missing_params.append("file_path")
                if not params.get("operation"):
                    missing_params.append("operation")
                if not params.get("target") and params.get("operation") != "append":
                    missing_params.append("target")
                if not params.get("content") and params.get("operation") in ["replace", "append", "insert_before", "insert_after"]:
                    missing_params.append("content")
                
                if missing_params:
                    error_msg = f"Missing required parameters: {', '.join(missing_params)}"
                    results["file_editor_tool"] = {"success": False, "message": error_msg}
                    tools_summary_list.append(f"File_Editor_Tool => {error_msg} | Received: {json.dumps(params)}")
                else:
                    file_path = params.get("file_path")
                    operation = params.get("operation")
                    target = params.get("target", "")
                    content = params.get("content", "")
                    occurrence = params.get("occurrence", "first")
                    
                    result = self.file_editor_tool.execute(
                        file_path=file_path,
                        operation=operation,
                        target=target,
                        content=content,
                        occurrence=occurrence
                    )
                    
                    results["file_editor_tool"] = result
                    
                    preview = f"operation={operation}, target='{str(target)[:20]}...'" if len(str(target)) > 20 else f"operation={operation}, target='{target}'"
                    summary_text = f"File_Editor_Tool => edited {file_path} ({preview})"
                    
                    tools_summary_list.append(summary_text)
        else:
            results["file_editor_tool"] = None

        # ===== End: Organize output data, update data collection history in context =====
        output_data = {
            "finish": finish,
            "tool_results": results,
            "summary": " | ".join(tools_summary_list) if tools_summary_list else "No tools used."
        }

        # Update data collection history in context.json if path is provided
        if context_path and os.path.exists(context_path):
            try:
                with open(context_path, "r", encoding="utf-8") as f:
                    context = json.load(f)
                
                # Ensure data_collection_history exists
                if "data_collection_history" not in context:
                    context["data_collection_history"] = []
                
                # Add new entry
                entry = {
                    "timestamp": self._get_timestamp(),
                    "summary": output_data["summary"],
                }
                
                # Add data point if provided
                if data_point:
                    entry["data_point"] = data_point
                
                # Optimize storage of tool call details to reduce context size
                # Only store detailed results for important tools or if finish=True
                details = {
                    "call_data": call_data,
                    "results": {}
                }
                
                # Simplified results - only include success status and basic info for non-final calls
                if not finish:
                    for tool_name, tool_result in results.items():
                        if tool_result is not None:
                            if isinstance(tool_result, dict):
                                # Store only success status and message for most tools
                                details["results"][tool_name] = {
                                    "success": tool_result.get("success"),
                                    "message": tool_result.get("message", "")[:100] + "..." if tool_result.get("message", "") and len(tool_result.get("message", "")) > 100 else tool_result.get("message", "")
                                }
                            else:
                                details["results"][tool_name] = str(tool_result)[:100] + "..." if len(str(tool_result)) > 100 else str(tool_result)
                else:
                    # For final calls, keep all details
                    details["results"] = results
                
                entry["details"] = details
                context["data_collection_history"].append(entry)
                
                # Limit history size to prevent context explosion
                # Keep more recent entries (more relevant) and remove older ones if too many
                if len(context["data_collection_history"]) > 50:  # Arbitrary limit
                    # Sort by timestamp to keep most recent
                    context["data_collection_history"].sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                    # Keep only the 50 most recent entries
                    context["data_collection_history"] = context["data_collection_history"][:50]
                    print(f"[ToolHandler] Trimmed data_collection_history to 50 most recent entries")
                
                # Write updated context
                with open(context_path, "w", encoding="utf-8") as f:
                    json.dump(context, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[ToolHandler] Error updating context.json: {e}")

        return output_data
    
    def _get_timestamp(self):
        """Get current timestamp in ISO format"""
        import datetime
        return datetime.datetime.now().isoformat()
    
    def inject_tool_metadata(self, tools_definition):
        """
        Inject tool metadata into tool definitions
        
        Args:
            tools_definition: Original tools schema definition
            
        Returns:
            Enhanced tools schema with metadata
        """
        tools_def_copy = deepcopy(tools_definition)
        
        for tool_def in tools_def_copy:
            if tool_def.get("name") == "multi_tools_executor":
                parameters_def = tool_def.get("parameters", {})
                props = parameters_def.get("properties", {})
                for prop_key, prop_val in props.items():
                    if prop_key in self.tool_map:
                        tool_obj = self.tool_map[prop_key]
                        
                        # Skip tools that are not initialized
                        if tool_obj is None:
                            prop_val["description"] = f"{prop_val.get('description', '')} (NOT AVAILABLE)"
                            continue
                        
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
        
        return tools_def_copy
    
    def check_available_tools(self):
        """
        Check which tools are available and which are not
        
        Returns:
            Tuple of (available_tools, unavailable_tools)
        """
        available_tools = []
        unavailable_tools = []
        
        for tool_name, tool in self.tool_map.items():
            if tool is None:
                unavailable_tools.append(tool_name)
            else:
                available_tools.append(tool_name)
        
        return available_tools, unavailable_tools
    
    def get_tool(self, tool_name):
        """Get tool object by name"""
        return self.tool_map.get(tool_name)
    
    def list_tools(self):
        """List all tool names"""
        return list(self.tool_map.keys()) 