import os
import json
import pandas as pd
from PyPDF2 import PdfReader
import pymupdf

from .base import BaseTool

class File_Reader_Tool(BaseTool):
    require_llm_engine = False
    
    def __init__(self):
        super().__init__(
            tool_name = "File_Reader_Tool",
            tool_description = "A tool that reads and processes various file formats (json, csv, txt, etc.), returning structured text in the file. Contents are limited to 50,000 characters per read.",
            tool_version = "1.0.0",
            input_types = {"file_path": "str - The path to the file from the current workspace."},
            output_type = "str - The extracted or structured content of the file (limited to 50,000 characters).",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(file_path="workspace/sample.txt")',
                    "description": "Read the content of a text file."
                },
                {
                    "command": 'execution = tool.execute(file_path="workspace/sample.csv")',
                    "description": "Read the content of a CSV file."
                },
            ],
            user_metadata = {
                "limitation": "Limited to 50,000 characters maximum. May not accurately process encrypted, corrupted, or highly complex file structures.",
                "best_practice": "Use this tool for reading standard file formats with structured or plain text content. For pdf files, consider using the PDF_Parser_Tool. For large files, consider reading specific sections or using multiple calls."
            },
        )

    def execute(self, file_path):
        """
        Read a file from the workspace, returning its content if supported.
        Returns a dict: { "success": bool, "message": str }.

        - success: True if read successfully, False if there's an error or invalid path.
        - message: The file content (if success, limited to 50,000 characters) or error message (if not).
        """
        MAX_CHARS = 50000  # 设置最大字符限制
        
        try:
            # Ensure the path starts from the workspace
            workspace_path = os.getenv("WORKSPACE_PATH")
            if "workspace" not in file_path:
                file_path = os.path.join(workspace_path, file_path)
            else:
                file_path = os.path.join(workspace_path, file_path.split("workspace/")[-1])

            if not os.path.isfile(file_path):
                return {
                    "success": False,
                    "message": "Error: Invalid file path."
                }

            file_extension = os.path.splitext(file_path)[-1].lower()

            # import here or at the top of the file, depending on your structure
            import pandas as pd
            from PyPDF2 import PdfReader
            import fitz as pymupdf   # if you're using pymupdf

            # Try different file types:
            if file_extension in [".json"]:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = json.load(f)
                result = json.dumps(content, indent=4, ensure_ascii=False)
                if len(result) > MAX_CHARS:
                    result = result[:MAX_CHARS] + "\n... [Content truncated due to 50,000 character limit] ..."
                return {
                    "success": True,
                    "message": result
                }

            elif file_extension in [".jsonl"]:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = []
                    total_length = 0
                    for line in f:
                        data = json.loads(line)
                        formatted_line = json.dumps(data, indent=4, ensure_ascii=False)
                        if total_length + len(formatted_line) > MAX_CHARS:
                            lines.append("\n... [Content truncated due to 50,000 character limit] ...")
                            break
                        lines.append(formatted_line)
                        total_length += len(formatted_line)
                return {
                    "success": True,
                    "message": "\n".join(lines)
                }

            elif file_extension in [".csv", ".tsv", ".xls", ".xlsx"]:
                if file_extension in [".csv", ".tsv"]:
                    sep = "\t" if file_extension == ".tsv" else ","
                    df = pd.read_csv(file_path, sep=sep)
                else:
                    df = pd.read_excel(file_path)
                result = df.to_string()
                if len(result) > MAX_CHARS:
                    result = result[:MAX_CHARS] + "\n... [Content truncated due to 50,000 character limit] ..."
                return {
                    "success": True,
                    "message": result
                }

            elif file_extension == ".pdf":
                try:
                    reader = PdfReader(file_path)
                    text = ""
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text and len(text) + len(page_text) <= MAX_CHARS:
                            text += page_text + "\n"
                        elif len(text) + len(page_text) > MAX_CHARS:
                            text += page_text[:MAX_CHARS-len(text)] + "\n... [Content truncated due to 50,000 character limit] ..."
                            break
                except:
                    doc = pymupdf.open(file_path)
                    text = ""
                    for page in doc:
                        page_text = page.get_text()
                        if len(text) + len(page_text) <= MAX_CHARS:
                            text += page_text + "\n"
                        else:
                            text += page_text[:MAX_CHARS-len(text)] + "\n... [Content truncated due to 50,000 character limit] ..."
                            break
                return {
                    "success": True,
                    "message": text
                }

            elif file_extension in [".html", ".xml"]:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read(MAX_CHARS + 1)  # 读取比限制多1个字符以检测是否超出限制
                if len(text) > MAX_CHARS:
                    text = text[:MAX_CHARS] + "\n... [Content truncated due to 50,000 character limit] ..."
                return {
                    "success": True,
                    "message": text
                }

            elif file_extension in [".md", ".txt", ".docx", ".rtf"]:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read(MAX_CHARS + 1)  # 读取比限制多1个字符以检测是否超出限制
                if len(text) > MAX_CHARS:
                    text = text[:MAX_CHARS] + "\n... [Content truncated due to 50,000 character limit] ..."
                return {
                    "success": True,
                    "message": text
                }

            else:
                # fallback
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read(MAX_CHARS + 1)
                if len(text) > MAX_CHARS:
                    text = text[:MAX_CHARS] + "\n... [Content truncated due to 50,000 character limit] ..."
                return {
                    "success": True,
                    "message": text
                }

        except Exception as e:
            # fallback attempt, or final error
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    fallback_text = f.read(MAX_CHARS + 1)
                if len(fallback_text) > MAX_CHARS:
                    fallback_text = fallback_text[:MAX_CHARS] + "\n... [Content truncated due to 50,000 character limit] ..."
                return {
                    "success": False,
                    "message": f"Partial read fallback:\n{fallback_text}"
                }
            except:
                return {
                    "success": False,
                    "message": f"Error reading file: {str(e)}"
                }


if __name__ == "__main__":
    import json
    
    tool = File_Reader_Tool()
    
    # Example file path
    relative_file_path = "workspace/sample.json"
    
    try:
        execution = tool.execute(file_path=relative_file_path)
        print("File Content:")
        print(json.dumps(execution, indent=4))
    except Exception as e:
        print(f"Execution failed: {e}")
    
    print("Done!")