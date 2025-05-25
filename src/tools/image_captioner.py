import os
from .base import BaseTool
from .engine import ChatOpenAI

class Image_Captioner_Tool(BaseTool):
    require_llm_engine = True
    
    def __init__(self, model_string="gpt-4o"):
        super().__init__(
            tool_name="Image_Captioner_Tool",
            tool_description="A tool that generates captions for images using OpenAI's multimodal model.",
            tool_version="1.0.0",
            input_types={
                "image": "str - The path to the image file from current workspace.",
                "prompt": "str - The prompt to guide the image captioning (default: 'Describe this image in detail.').",
            },
            output_type="str - The generated caption for the image.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(image="workspace/path/to/image.png")',
                    "description": "Generate a caption for an image using the default prompt and model."
                },
                {
                    "command": 'execution = tool.execute(image="workspace/path/to/image.png", prompt="Explain the geometric shapes in the image.")',
                    "description": "Generate a caption focusing on geometric shapes demonstrated in the image."
                }
            ],
            user_metadata = {
                "limitation": "The Image_Captioner_Tool may misinterpret complex equations, symbols, or spatial relationships, leading to inaccurate descriptions.",
                "best_practice": "Please consider to use it on images with clear and simple content to help you understand the modeling problem, instead of using it for complex data analysis.",
            },
        )
        print(f"\nInitializing Image Captioner Tool with model: {model_string}")
        self.llm_engine = ChatOpenAI(model_string=model_string, is_multimodal=True) if model_string else None

    def execute(self, image, prompt="Describe this image in detail."):
        """
        Generate a caption or description for an image using a multimodal LLM engine.
        Returns a dict: { "success": bool, "message": str }.

        - success: True if caption generation was successful, False otherwise.
        - message: The caption text (if success) or an error message.
        """
        try:
            # Check if LLM engine is initialized
            if not self.llm_engine:
                return {
                    "success": False,
                    "message": "Error: LLM engine not initialized. Please provide a valid model_string."
                }

            input_data = [prompt]

            # get workspace path from environment
            workspace_path = os.getenv("WORKSPACE_PATH", "workspace")

            # ensure the image path is relative to workspace
            if "workspace" not in image:
                image_path = os.path.join(workspace_path, image)
            else:
                # remove "workspace/" from the path, then join with workspace_path
                image_path = os.path.join(workspace_path, image.split("workspace/")[-1])

            # Check if the file exists
            if not os.path.isfile(image_path):
                return {
                    "success": False,
                    "message": "Error: Invalid image file path."
                }

            # Attempt to read the image file
            try:
                with open(image_path, 'rb') as file:
                    image_bytes = file.read()
                input_data.append(image_bytes)
            except Exception as e:
                return {
                    "success": False,
                    "message": f"Error reading image file: {str(e)}"
                }

            # Attempt to generate caption
            try:
                caption = self.llm_engine(input_data)
                return {
                    "success": True,
                    "message": caption
                }
            except Exception as e:
                return {
                    "success": False,
                    "message": f"Error generating caption using LLM engine: {str(e)}"
                }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error generating caption: {str(e)}"
            }

    def get_metadata(self):
        metadata = super().get_metadata()
        metadata['require_llm_engine'] = self.require_llm_engine # NOTE: can be removed if not needed
        return metadata


if __name__ == "__main__":
    import json
    
    tool = Image_Captioner_Tool(model_string="gpt-4o")

    # Get tool metadata
    metadata = tool.get_metadata()
    print(metadata)
    
    # Construct the full path to the image using the script's directory
    relative_image_path = "workspace/Figure1.jpg"

    # Execute the tool with default prompt
    try:
        execution = tool.execute(image=relative_image_path)
        print("Generated Caption:")
        print(json.dumps(execution, indent=4)) 
    except Exception as e: 
        print(f"Execution failed: {e}")

    print("Done!")