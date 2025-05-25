import os
from .base import BaseTool

class File_Lister_Tool(BaseTool):
    require_llm_engine = False
    
    def __init__(self):
        super().__init__(
            tool_name="File_Lister_Tool",
            tool_description="A tool that lists all files in a given directory recursively.",
            tool_version="1.0.0",
            input_types={"dir_path": "str - The directory path starting from the workspace (default: workspace/)."},
            output_type="str - A list of all files under the directory with their paths, indicating file or folder type.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(dir_path="workspace/")',
                    "description": "List all files under the current workspace directory."
                }
            ],
            user_metadata={
                "limitation": "May not work properly if the directory contains restricted access files.",
                "best_practice": "Use this tool for listing files in structured directories to check what is present in the workspace or before writing to a certain file."
            },
        )
    
    def execute(self, dir_path="workspace/"):
        """
        List the files under the given dir_path (relative to WORKSPACE_PATH).
        Returns a dict with { 'success': bool, 'message': str }.

        Enhancement:
          - If it's a folder, append "(folder)"
          - If it's a file with an extension, show "(.{ext})"
          - If it's a file without extension, just "(file)"
          - If the path is not a directory but is a file, return an error.
        """
        try:
            # Ensure the path starts from the workspace
            workspace_path = os.getenv("WORKSPACE_PATH")
            if dir_path == "workspace":
                dir_path = "workspace/"
            if "workspace" not in dir_path:
                dir_path = os.path.join(workspace_path, dir_path)
            else:
                # remove "workspace/" from dir_path, then join with workspace_path
                dir_path = os.path.join(workspace_path, dir_path.split("workspace/")[-1])
            
            if not os.path.isdir(dir_path):
                # 如果不是目录，但却是文件，则报错提示
                if os.path.isfile(dir_path):
                    return {
                        "success": False,
                        "message": "Error: The path points to a file, not a directory."
                    }
                else:
                    return {
                        "success": False,
                        "message": "Error: Invalid directory path."
                    }
            
            file_structure = []

            def list_files(current_path, prefix=""):
                entries = sorted(os.listdir(current_path))
                for index, entry in enumerate(entries):
                    full_path = os.path.join(current_path, entry)
                    is_last = (index == len(entries) - 1)
                    new_prefix = prefix + ("    " if is_last else "|   ")
                    relative_path = os.path.relpath(full_path, workspace_path)

                    if os.path.isdir(full_path):
                        # It's a folder
                        file_structure.append(f"{prefix}|-- {entry} (folder)")
                        # Recursively list folder contents
                        list_files(full_path, new_prefix)
                    else:
                        # It's a file -> check extension
                        base_name, ext = os.path.splitext(entry)
                        if ext:
                            extension_without_dot = ext[1:]
                            file_structure.append(
                                f"{prefix}|-- {entry} (.{extension_without_dot}) (path: workspace/{relative_path})"
                            )
                        else:
                            file_structure.append(
                                f"{prefix}|-- {entry} (file) (path: workspace/{relative_path})"
                            )

            # First add the root directory name
            relative_path = os.path.relpath(dir_path, workspace_path)
            if relative_path.strip() == ".":
                output = "workspace"
            else:
                output = os.path.basename(dir_path)

            # Recursively build the structure
            list_files(dir_path)

            # Combine results
            output += "\n" + "\n".join(file_structure)

            return {
                "success": True,
                "message": output
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error listing files: {str(e)}"
            }


if __name__ == "__main__":
    tool = File_Lister_Tool()
    
    # Example directory path
    relative_dir_path = "workspace/sample"
    
    try:
        execution = tool.execute(dir_path=relative_dir_path)
        if execution["success"]:
            print("File List:")
            print(execution["message"])
        else:
            print("Error:", execution["message"])
    except Exception as e:
        print(f"Execution failed: {e}")
    
    print("Done!")
