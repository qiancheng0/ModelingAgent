import os
import tempfile
import subprocess
import threading

from .base import BaseTool

class Python_Execution_Tool(BaseTool):
    require_llm_engine = False
    
    def __init__(self):
        super().__init__(
            tool_name="Python_Execution_Tool",
            tool_description="A tool that executes Python code from a file or provided content, handling errors and timeouts.",
            tool_version="1.0.0",
            input_types={
                "file_path": "str - The path to the Python file from the workspace (default to 'workspace/temp.py').",
                "code_content": "str -  The Python code to execute. If provided, it will overwrite the file or be executed from a temp file."
            },
            output_type="str - The output or error messages from executing the code.",
            demo_commands=[
                {
                    "command": "execution = tool.execute(file_path='workspace/script.py')",
                    "description": "Execute an existing Python script."
                },
                {
                    "command": "execution = tool.execute(code_content='print(\"Hello, World!\")')",
                    "description": "Execute provided Python code directly."
                }
            ],
            user_metadata={
                "limitation": "Any error encountered will be returned. This tool will faithfully execute what you provide or what is in the code file, without any validation or refining. ⚠️ The current sandbox environment **does NOT allow installing new Python packages**, especially those that require compiling native C/C++ libraries (e.g., GDAL/GEOS/PROJ). Your code should use pure python, not anythings using g++. You can use numpy, pandas, scipy, etc.",
                "best_practice": "If the code content is given, ensure it is well structured and is directly executable. If the file path is provided, ensure the file exists and is a valid Python script.\nEnsure in the code file path should all be relative path within the workspace. Use this tool for quick code execution and experiment."
            },
        )
    
    def execute(self, file_path=None, code_content=None):
        """
        Execute Python code from file_path or code_content.
        Returns a dict: { "success": bool, "message": str }.

        - success: True if code executed without 'Error:' or 'Time limit exceeded' in output.
                False otherwise (including invalid file path, exception, etc.)
        - message: The output or error message string.
        """
        # Quick checks
        if not file_path and not code_content:
            return {
                "success": False,
                "message": "Error: Either file_path or code_content must be provided."
            }

        workspace_path = os.getenv("WORKSPACE_PATH", "workspace")
        execution_file = None

        if file_path:
            if "workspace" not in file_path:
                file_path = os.path.join(workspace_path, file_path)
            else:
                file_path = os.path.join(workspace_path, file_path.split("workspace/")[-1])

        try:
            if code_content:
                # If code_content is given:
                # 1) if file_path is also provided, we write code_content to that file
                # 2) else we create a temp file
                if file_path:
                    execution_file = file_path
                    with open(execution_file, "w", encoding="utf-8") as f:
                        f.write(code_content)
                else:
                    import tempfile
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".py", dir=workspace_path)
                    execution_file = temp_file.name
                    print(f"Temporary file created: {execution_file}")
                    with open(execution_file, "w", encoding="utf-8") as f:
                        f.write(code_content)
                    temp_file.close()
            else:
                # code_content is None => must run an existing Python file
                execution_file = file_path
                if not os.path.isfile(execution_file):
                    return {
                        "success": False,
                        "message": "Error: Provided file path does not exist."
                    }

            # We'll use a dictionary to store the output
            result = {"output": "Execution Error: Time limit exceeded."}

            def run_code():
                try:
                    result["output"] = subprocess.check_output(
                        ["python", execution_file],
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=15
                    )
                except subprocess.TimeoutExpired:
                    result["output"] = "Execution Error: Time limit exceeded."
                except subprocess.CalledProcessError as e:
                    result["output"] = f"Execution Error: {e.output}"
                except Exception as e:
                    result["output"] = f"Unexpected Error: {str(e)}"

            execution_thread = threading.Thread(target=run_code)
            execution_thread.start()
            execution_thread.join(timeout=15)

            # Check if result contains errors
            out_str = result["output"]
            # Simple check: if contains "Error:" or "Time limit exceeded" then failed
            # You can refine this check as needed
            if "Error:" in out_str or "time limit exceeded" in out_str.lower():
                return {
                    "success": False,
                    "message": out_str
                }
            else:
                return {
                    "success": True,
                    "message": out_str
                }

        except Exception as e:
            # If error occurs elsewhere in try block, also return error
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
        finally:
            # Cleanup temp file if used
            if code_content and not file_path and execution_file:
                os.remove(execution_file)


if __name__ == "__main__":
    tool = Python_Execution_Tool()
    execution = tool.execute(file_path="workspace/output.py")
    print("Execution Output:")
    print(execution)