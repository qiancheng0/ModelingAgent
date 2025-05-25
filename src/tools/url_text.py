import os
import requests
from bs4 import BeautifulSoup

from .base import BaseTool

class URL_Text_Extractor_Tool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_name="URL_Text_Extractor_Tool",
            tool_description="A tool that extracts all text from a given URL.",
            tool_version="1.0.0",
            input_types={
                "url": "str - The URL from which to extract text.",
            },
            output_type="str - The extracted text from the given url and any error messages.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(url="https://example.com")',
                    "description": "Extract all text from the example.com website."
                },
                {
                    "command": 'execution = tool.execute(url="https://en.wikipedia.org/wiki/Python_(programming_language)")',
                    "description": "Extract all text from the Wikipedia page about Python programming language."
                },
            ],
            user_metadata={
                "limitation": "1. The URL_Text_Extractor_Tool may not accurately extract text from all websites. The extracted text may contain errors or omissions. The text in the images or embedded content may not be extracted. 2. You should not use this tool to download anything or read online document like PDF. Make sure that the url you entered is a website.",
                "best_practice": "Use this tool to summarize all the text information from a web page. The extracted text should be used as a reference for understanding the content of the website. Be aware that it may not be exactly complete or accurate."
            }
        )

    def extract_text_from_url(self, url):
        try:
            response = requests.get(url, timeout=10)  # optional: set a timeout
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            text = soup.get_text(separator='\n', strip=True)
            text = text[:10000]  # Limit the text to 10000 characters
            return {
                "success": True,
                "message": text
            }
        except requests.RequestException as e:
            return {
                "success": False,
                "message": f"Error fetching URL: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error extracting text: {str(e)}"
            }

    def execute(self, url):
        """
        Extract text from a given webpage URL, returning a dict:
          { "success": bool, "message": str }.

        - success=True, message=extracted_text (trimmed if too long)
        - success=False, message=error info
        """
        return self.extract_text_from_url(url)
    
    def get_metadata(self):
        metadata = super().get_metadata()
        return metadata


if __name__ == "__main__":
    # Example usage of the URL_Text_Extractor_Tool
    tool = URL_Text_Extractor_Tool()

    # Get tool metadata
    metadata = tool.get_metadata()
    print(metadata)

    # Sample URL for extracting text
    url = "https://weather.metoffice.gov.uk/forecast/wx4g092se"

    import json

    # Execute the tool with the sample URL
    try:
        execution = tool.execute(url=url)
        print("Execution Result:")
        print(execution)
    except ValueError as e:
        print(f"Execution failed: {e}")

    print("Done!")