import os
from .base import BaseTool
from .engine import ChatOpenAI

class Solution_Generator_Tool(BaseTool):
    require_llm_engine = True

    def __init__(self, model_string="gpt-4o"):
        super().__init__(
            tool_name="Generalist_Solution_Generator_Tool",
            tool_description="A generalized tool that takes query from the user as prompt, and answers the question step by step to the best of its ability. It can also accept an image.",
            tool_version="1.0.0",
            input_types={
                "prompt": "str - The prompt that includes query from the user to guide the agent to generate response (Examples: 'Describe this image in detail').",
                "image": "str - The path to the image file from current workspace if applicable (default: None).",
            },
            output_type="str - The generated response to the original query prompt",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(prompt="Summarize the following text in a few lines")',
                    "description": "Generate a short summary given the prompt from the user."
                },
                {
                    "command": 'execution = tool.execute(prompt="Give your best coordinate estimate for the pacemaker in the image and return (x1, y1, x2, y2)", image="workspace/path/to/image.png")',
                    "description": "Generate bounding box coordinates given the image and prompt from the user. The format should be (x1, y1, x2, y2)."
                },
            ],

            user_metadata = {
                "limitation": "The Solution_Generator_Tool may provide hallucinated or incorrect responses. Besides, the solution generator can only answer SIMPLE questions. Never throw whole question into this tool and expect a proper response.",
                "best_practice": "Use the Solution_Generator_Tool for general queries or tasks that don't require specialized knowledge or other specific tools. Provide clear, specific prompts. For complex queries, break them down into subtasks before using this tool."
            }

        )
        self.model_string = model_string  

    def execute(self, prompt, image=None):
        """
        Generates a solution or answer using a ChatOpenAI model (optionally multimodal).
        Returns a dict: { "success": bool, "message": str }.

        - success: True if generation succeeded, False otherwise.
        - message: The generated text or error message.
        """
        print(f"\nInitializing Solution Tool with model: {self.model_string}")
        multimodal = True if image else False

        try:
            # Initialize the LLM engine
            from src.tools.engine import ChatOpenAI  # or import wherever ChatOpenAI is
            llm_engine = ChatOpenAI(model_string=self.model_string, is_multimodal=multimodal)
        except Exception as e:
            return {
                "success": False,
                "message": f"Error initializing ChatOpenAI engine: {str(e)}"
            }

        try:
            input_data = [prompt]
            if multimodal:
                if not os.path.isfile(image):
                    return {
                        "success": False,
                        "message": "Error: Invalid image file path."
                    }
                try:
                    with open(image, 'rb') as file:
                        image_bytes = file.read()
                    input_data.append(image_bytes)
                except Exception as e:
                    return {
                        "success": False,
                        "message": f"Error reading image file: {str(e)}"
                    }
                # Attempt generating with multimodal
                response = llm_engine(input_data)
            else:
                # Text-only
                response = llm_engine(input_data[0])

            return {
                "success": True,
                "message": response
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error generating response: {str(e)}"
            }

    def get_metadata(self):
        metadata = super().get_metadata()
        return metadata

if __name__ == "__main__":
    # Example usage of the Generalist_Tool
    tool = Solution_Generator_Tool(model_string="gpt-4o")

    # Get tool metadata
    metadata = tool.get_metadata()
    print(metadata)

    # Construct the full path to the image using the script's directory
    relative_image_path = "workspace/Figure1.jpg"
    prompt = "Describe the image in detail."

    # Execute the tool with default prompt
    try:
        execution = tool.execute(prompt=prompt, image=relative_image_path)
        # execution = tool.execute(prompt=prompt)
        print("Generated Response:")
        print(execution)
    except Exception as e: 
        print(f"Execution failed: {e}")

    print("Done!")