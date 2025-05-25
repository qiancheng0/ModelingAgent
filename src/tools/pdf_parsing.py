import os
from .base import BaseTool
from PyPDF2 import PdfReader
import pymupdf
import pymupdf4llm

class PDF_Parser_Tool(BaseTool):
    require_llm_engine = False
    
    def __init__(self):
        super().__init__(
            tool_name="PDF_Parser_Tool",
            tool_description="A tool that extracts and processes text from PDF documents.",
            tool_version="1.0.0",
            input_types={
                "pdf_path": "str - The path to the PDF file from the current workspace.",
                "num_pages": "int - The number of pages to extract (default: all pages).",
                "min_size": "int - The minimum text length required for extraction (default: 100)."
            },
            output_type="str - The extracted text from the PDF document.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(pdf_path="workspace/sample.pdf")',
                    "description": "Extract text from an entire PDF document."
                },
                {
                    "command": 'execution = tool.execute(pdf_path="workspace/sample.pdf", num_pages=2, min_size=50)',
                    "description": "Extract text from the first two pages of a PDF with a minimum text length of 50 characters."
                }
            ],
            user_metadata={
                "limitation": "May not accurately extract text from scanned PDFs or those with complex formatting. The extracted text may contain errors or omissions.",
                "best_practice": "Use this tool for extracting text from digital PDFs rather than scanned images."
            },
        )
        print("\nInitializing PDF Parser Tool")
    
    def execute(self, pdf_path, num_pages=None, min_size=-1):
        """
        Extract text from a PDF using multiple fallback methods (pymupdf4llm -> pymupdf -> pypdf).
        Returns a dict with { "success": bool, "message": str }:
        - success=True, message=extracted_text on success
        - success=False, message=error info on fail
        """
        
        if type(num_pages) == str:
            num_pages == int(num_pages) if num_pages.isdigit() else None
        if type(min_size) == str:
            min_size = int(min_size) if min_size.isdigit() else -1
        
        try:
            # Ensure the path starts from the workspace
            workspace_path = os.getenv("WORKSPACE_PATH", "workspace")
            if "workspace" not in pdf_path:
                pdf_path = os.path.join(workspace_path, pdf_path)
            else:
                pdf_path = os.path.join(workspace_path, pdf_path.split("workspace/")[-1])

            if not os.path.isfile(pdf_path):
                return {
                    "success": False,
                    "message": "Error: Invalid PDF file path."
                }

            text = ""

            try:
                # Attempt using pymupdf4llm
                if num_pages is None:
                    text = pymupdf4llm.to_markdown(pdf_path)
                else:
                    reader = PdfReader(pdf_path)
                    min_pages = min(len(reader.pages), num_pages)
                    text = pymupdf4llm.to_markdown(pdf_path, pages=list(range(min_pages)))

                if min_size != -1 and len(text) < min_size:
                    raise Exception("Text too short")

            except Exception as e:
                print(f"Error with pymupdf4llm, falling back to pymupdf: {e}")
                try:
                    # Fallback to pure pymupdf
                    doc = pymupdf.open(pdf_path)
                    if num_pages:
                        doc = doc[:num_pages]
                    text = "".join(page.get_text() for page in doc)

                    if min_size != -1 and len(text) < min_size:
                        raise Exception("Text too short")

                except Exception as e2:
                    print(f"Error with pymupdf, falling back to pypdf: {e2}")
                    # Fallback to pypdf
                    reader = PdfReader(pdf_path)
                    if num_pages is None:
                        text = "".join(page.extract_text() for page in reader.pages)
                    else:
                        text = "".join(
                            page.extract_text() for page in reader.pages[:num_pages]
                        )

                    if min_size != -1 and len(text) < min_size:
                        raise Exception("Text too short")

            # If everything is ok, return success + text
            return {
                "success": True,
                "message": text
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error extracting text: {str(e)}"
            }

    def get_metadata(self):
        metadata = super().get_metadata()
        metadata['require_llm_engine'] = self.require_llm_engine
        return metadata

if __name__ == "__main__":
    import json

    tool = PDF_Parser_Tool()
    
    # Get tool metadata
    metadata = tool.get_metadata()
    print(metadata)
    
    # Construct the full path to the PDF using the script's directory
    os.environ["WORKSPACE_PATH"] = "PATH_TO_TEST_FILE/2025_Managing_Sustainable_Tourism"
    relative_pdf_path = "workspace/2025_MCM_Problem_B.pdf"
    
    # Execute the tool with default parameters
    try:
        execution = tool.execute(pdf_path=relative_pdf_path)
        print("Extracted Text:")
        print(json.dumps(execution, indent=4))
    except Exception as e:
        print(f"Execution failed: {e}")
    
    print("Done!")