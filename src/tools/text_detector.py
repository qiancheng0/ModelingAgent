import os
import time
from .base import BaseTool

import warnings
warnings.filterwarnings("ignore")

class Text_Detector_Tool(BaseTool):
    require_llm_engine = False
    
    def __init__(self):
        super().__init__(
            tool_name="Text_Detector_Tool",
            tool_description="A tool that detects text in an image using EasyOCR.",
            tool_version="1.0.0",
            input_types={
                "image": "str - The path to the image file from the current workspace.",
                "languages": "list - A list of language codes for the OCR model (default to English and Simplified Chinese only).",
                "detail": "int - The level of detail in the output. Set to 0 for simpler output, 1 for detailed output (default to 0 simpler output)."
            },
            output_type="list - A list of detected text blocks.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(image="workspace/path/to/image.png")',
                    "description": "Detect text in an image using the default language (English and Chinese)."
                },
                {
                    "command": 'execution = tool.execute(image="path/to/image.png", languages=["en"], detail=0)',
                    "description": "Detect English text in an image with simpler output (text without coordinates and scores)."
                },
            ],
            user_metadata={
                "limitation": "The Text_Detector_Tool may not accurately detect text in images with complex layouts, fonts, or backgrounds. The tables, numbers, and special characters may not be detected or retain its original structure.",
                "best_practice": "Use the Text_Detector_Tool for detecting text in simple images with clear text. try to post process the detected text to improve accuracy and readability. Use the extracted text only as reference for understanding the image content.",
                "frequently_used_language": {
                    "ch_sim": "Simplified Chinese",
                    "ch_tra": "Traditional Chinese",
                    "de": "German",
                    "en": "English",
                    "es": "Spanish",
                    "fr": "French",
                    "hi": "Hindi",
                    "ja": "Japanese",
                }
            }
        )

    def build_tool(self, languages=None):
        """
        Builds and returns the EasyOCR reader model.

        Parameters:
            languages (list): A list of language codes for the OCR model.

        Returns:
            easyocr.Reader: An initialized EasyOCR Reader object.
        """
        languages = languages or ["en"]  # Default to English if no languages provided
        
        try:
            import easyocr
            reader = easyocr.Reader(languages)
            return reader
        except ImportError:
            raise ImportError("Please install the EasyOCR package using 'pip install easyocr'.")
        except Exception as e:
            print(f"Error building the OCR tool: {e}")
            return None
    
    def execute(self, image, languages=None, max_retries=10, retry_delay=5, clear_cuda_cache=False, **kwargs):
        """
        Executes the OCR tool to detect text in the provided image.

        Parameters:
            image (str): The path to the image file.
            languages (list): A list of language codes for the OCR model.
            max_retries (int): Maximum number of retry attempts.
            retry_delay (int): Delay in seconds between retry attempts.
            clear_cuda_cache (bool): Whether to clear CUDA cache on out-of-memory errors.
            **kwargs: Additional keyword arguments for the OCR reader.

        Returns:
            dict: {
            "success": bool,
            "message": str,  # success/failure info
            "data": list     # OCR result list (empty if failed)
            }
        """
        languages = ["en"]

        # get workspace path from environment
        workspace_path = os.getenv("WORKSPACE_PATH", "workspace")
        if "workspace" not in image:
            image = os.path.join(workspace_path, image)
        else:
            image = os.path.join(workspace_path, image.split("workspace/")[-1])

        # Check if file exists
        if not os.path.isfile(image):
            return {
                "success": False,
                "message": "Error: Invalid image file path.",
                "data": []
            }

        # Retry up to max_retries times
        for attempt in range(max_retries):
            try:
                reader = self.build_tool(languages)
                if reader is None:
                    return {
                        "success": False,
                        "message": "Error: Failed to build the OCR tool.",
                        "data": []
                    }

                result = reader.readtext(image, **kwargs)
                try:
                    # If detail=1, convert numpy coords to int
                    cleaned_result = [
                        ([[int(coord[0]), int(coord[1])] for coord in item[0]], item[1], round(float(item[2]), 2))
                        for item in result
                    ]
                    return {
                        "success": True,
                        "message": "OCR detection succeeded.",
                        "data": cleaned_result
                    }
                except Exception:
                    # detail=0 or other fallback
                    return {
                        "success": True,
                        "message": "OCR detection succeeded (detail=0).",
                        "data": result
                    }

            except RuntimeError as e:
                if "CUDA out of memory" in str(e):
                    print(f"CUDA out of memory on attempt {attempt+1}.")
                    if clear_cuda_cache:
                        print("Clearing CUDA cache and retrying...")
                        import torch
                        torch.cuda.empty_cache()
                    else:
                        print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                else:
                    print(f"Runtime error: {e}")
                    return {
                        "success": False,
                        "message": f"Runtime error: {str(e)}",
                        "data": []
                    }
            except Exception as e:
                print(f"Error detecting text: {e}")
                return {
                    "success": False,
                    "message": f"Error detecting text: {str(e)}",
                    "data": []
                }

        # If we exhausted all retries
        print(f"Failed to detect text after {max_retries} attempts.")
        return {
            "success": False,
            "message": f"Failed after {max_retries} attempts.",
            "data": []
        }


    def get_metadata(self):
        """
        Returns the metadata for the Text_Detector_Tool.

        Returns:
            dict: A dictionary containing the tool's metadata.
        """
        metadata = super().get_metadata()
        return metadata


if __name__ == "__main__":
    import json
    
    # Example usage of the Text_Detector_Tool
    tool = Text_Detector_Tool()

    # Get tool metadata
    metadata = tool.get_metadata()
    print(metadata)

    relative_image_path = "workspace/Figure2.jpg"

    # Execute the tool
    try:
        execution = tool.execute(image=relative_image_path, languages=["en"], detail=0)
        print(json.dumps(execution))

        print("Detected Text:", execution)
    except ValueError as e:
        print(f"Execution failed: {e}")

    print("Done!")