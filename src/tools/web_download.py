import os
import requests
from .base import BaseTool

class Web_Download_Tool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_name="Web_Download_Tool",
            tool_description="A tool that downloads a file from a given URL and saves it to a specified location.",
            tool_version="1.0.0",
            input_types={
                "url": "str - The URL of the file to download.",
                "save_path": "str - The target save file path starting from the workspace, including the filename."
            },
            output_type="str - Success message or error details.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(url="https://arxiv.org/pdf/paper.pdf", save_path="workspace/paper.pdf")',
                    "description": "Download a PDF file from arXiv and save it to the workspace."
                }
            ],
            user_metadata={
                "limitation": "Cannot download files from restricted or inaccessible URLs. The downnload may fail if the URL is invalid or the file is too large. Always verify the content type matches the file extension - servers might return HTML error pages even when requesting non-HTML content (e.g., downloading a .zip but getting HTML content with .zip extension).",
                "best_practice": "Ensure the URL is valid and the save path includes the intended filename. Check the availability of the file after download using python code or other means."
            },
        )

    def execute(self, url, save_path):
        """
        Download a file from a URL to the workspace.

        Returns:
            dict: {
                "success": bool,
                "message": str   # success info or error message
            }
        """
        try:
            # Ensure the save path starts from the workspace
            workspace_path = os.getenv("WORKSPACE_PATH", "workspace")
            if not save_path.startswith("workspace/"):
                final_path = os.path.join(workspace_path, save_path)
            else:
                final_path = os.path.join(workspace_path, save_path.split("workspace/")[-1])

            # Create necessary directories
            os.makedirs(os.path.dirname(final_path), exist_ok=True)

            # Download the file
            import requests
            response = requests.get(url, stream=True, timeout=10)
            response.raise_for_status()  # Raise error for failed requests

            with open(final_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return {
                "success": True,
                "message": f"Download successful! The file is saved at {final_path}"
            }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "message": f"Download failed (RequestException): {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error saving file: {str(e)}"
            }

if __name__ == "__main__":
    tool = Web_Download_Tool()
    execution = tool.execute(url="https://arxiv.org/pdf/2502.01600", save_path="workspace/paper.pdf")
    print(execution)
