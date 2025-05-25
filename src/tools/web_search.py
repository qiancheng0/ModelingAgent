import os
import json
import http.client
import time

from .base import BaseTool

class Web_Search_Tool(BaseTool):
    require_llm_engine = False
    
    def __init__(self):
        super().__init__(
            tool_name="Web_Search_Tool",
            tool_description="A tool that performs web searches using an API and returns structured search results.",
            tool_version="1.0.0",
            input_types={
                "query": "str - The search query to retrieve information.",
                "link": "bool - Whether to include links in the output (default: True).",
                "num": "int - Number of search results to return (default: 10)."
            },
            output_type="str - The formatted search results based on the given query.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(query="Latest AI trends", link=True, num=5)',
                    "description": "Search for the latest AI trends and return up to 5 results with links."
                }
            ],
            user_metadata={
                "limitation": "Limited by API availability and may not always return results. The snippet may be very concise and may not contain all relevant information.",
                "best_practice": "Use this tool for retrieving up-to-date web search results on various topics. Then, use the search link you get from the return to explore more details by further using URL_Text_Extractor_Tool."
            }
        )

    def execute(self, query, link=False, num=10):
        """
        Perform a web search via Google Serper API.

        Returns:
        dict: {
            "success": bool,          # True if search results obtained, False otherwise
            "message": str            # The search results or error info
        }
        """
        
        if type(link) == str:
            link = False if link.lower() == 'false' else True
        if type(num) == str:
            num = int(num) if num.isdigit() else 10
        
        api_key = os.getenv("SERPER_API_KEY", None)
        if not api_key:
            return {
                "success": False,
                "message": "Error: Missing SERPER_API_KEY."
            }

        import http.client, json, time

        conn = http.client.HTTPSConnection("google.serper.dev")
        headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json'
        }
        payload = json.dumps({
            "q": query,
            # "tbs": "qdr:y"  # optional param for time range
        })

        try_time = 0
        data = {}
        while True:
            try:
                conn.request("POST", "/search", payload, headers)
                res = conn.getresponse()
                raw_data = res.read().decode("utf-8")
                data = json.loads(raw_data)

                if data.get("organic", []):
                    # We got some results, break
                    break

                try_time += 1
                if try_time > 5:
                    return {
                        "success": False,
                        "message": "Search Error: Timeout or no results after 5 attempts."
                    }
                time.sleep(5)

            except Exception as e:
                return {
                    "success": False,
                    "message": f"Search Error while sending request: {str(e)}"
                }

        try:
            output = ""
            index = 1
            answer_box = data.get("answerBox", {})

            # If there's an answerBox
            if answer_box:
                try:
                    current = f"{index}. {answer_box['title']}"
                    if link and 'link' in answer_box:
                        current += f"\n- Link: {answer_box['link']}"
                    if "date" in answer_box:
                        current += f"\n- Date: {answer_box['date']}"
                    current += f"\n- Snippet: {answer_box['snippet']}"
                    output += current + "\n\n"
                    index += 1
                except Exception:
                    pass  # in case something is missing

            # If we've reached the desired number of results
            if index > num:
                return {
                    "success": True,
                    "message": output.strip()
                }

            # Now handle the "organic" array
            for item in data.get("organic", []):
                try:
                    current = f"{index}. {item['title']}"
                    if link and 'link' in item:
                        current += f"\n- Link: {item['link']}"
                    if "date" in item:
                        current += f"\n- Date: {item['date']}"
                    current += f"\n- Snippet: {item['snippet']}"
                    output += current + "\n\n"
                    index += 1
                except:
                    pass

                if index > num:
                    return {
                        "success": True,
                        "message": output.strip()
                    }

            # Return what we have so far
            return {
                "success": True,
                "message": output.strip()
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Search Error: {str(e)}"
            }

if __name__ == "__main__":
    tool = Web_Search_Tool()
    query = "How's the weather in Beijing"
    execution = tool.execute(query=query, link=True, num=3)
    print("Search Results:")
    print(execution)
    print("Done!")
