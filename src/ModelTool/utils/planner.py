import sys
import os
import json
import time
import yaml
from openai import OpenAI

class BasePlanner:
    
    def __init__(self, planner_config, main_agent=None):
        self.main_agent = main_agent 

        self.model_name = planner_config.get("model_name", "gpt-4o-mini")
        openai_api_key = planner_config.get("openai_api_key", "")
        self.use_scratch_board = False

        self.planner_name = planner_config.get("planner_name", "BasePlanner")
        self.log_planner_steps = planner_config.get("log_planner_steps", True)

        if "gpt" in self.model_name.lower():
            self.client = OpenAI(api_key=openai_api_key)
            print(f"[BasePlanner] Initialized with model_name={self.model_name}, openai_api_key length={len(openai_api_key)}")
        else:
            port = planner_config["port"]
            self.client = OpenAI(api_key="dummy", base_url=f"http://localhost:{port}/v1")
            print(f"[BasePlanner] Initialized with model_name={self.model_name}, dummy client")

        self.tools_description = self._build_tools_description()
        
        if self.main_agent and hasattr(self.main_agent, "run_folder"):
            self.planner_log_file = os.path.join(
                self.main_agent.run_folder,
                f"planner.log"
            )
        print(f"[BasePlanner] Planner log will be saved to: {self.planner_log_file}")

    def _build_tools_description(self) -> str:
        if (self.main_agent is None) or (not hasattr(self.main_agent, "tool_map")):
            return "No tool information is available."

        lines = []
        for tool_key, tool_obj in self.main_agent.tool_map.items():
            tool_name = getattr(tool_obj, "tool_name", tool_key)
            tool_description = getattr(tool_obj, "tool_description", "")
            user_metadata = getattr(tool_obj, "user_metadata", {})

            block = (
                f"Tool Name: {tool_name}\n"
                f"Description: {tool_description}\n"
                f"User Metadata: {user_metadata}\n"
                "----------------------"
            )
            lines.append(block)

        return "\n".join(lines)

    def _append_planner_log(self, text: str):
        if self.log_planner_steps:
            with open(self.planner_log_file, "a", encoding="utf-8") as f:
                f.write(text + "\n")

    def gpt_planner_call(self, messages, max_char = 409600):
        total_len = sum(len(m["content"]) for m in messages)

        if total_len > max_char:
            self._append_planner_log(
                f"[Planner] Messages total length {total_len} exceeds {max_char}, now truncating."
            )

            for i in reversed(range(len(messages))):
                msg_len = len(messages[i]["content"])
                if total_len <= max_char:
                    break
                over_size = total_len - max_char
                if msg_len <= over_size:
                    messages[i]["content"] = ""
                    total_len -= msg_len
                else:
                    new_len = msg_len - over_size
                    messages[i]["content"] = messages[i]["content"][:new_len] + " ... (truncated)"
                    total_len = self.MAX_CHAR_LENGTH

        rounds = 0
        while True:
            rounds += 1
            try:
                system_content = ""
                user_content = ""
                for m in messages:
                    if m["role"] == "system":
                        system_content = m["content"]
                    elif m["role"] == "user":
                        user_content = m["content"]

                log_text = (
                    f"== [Planner Round {rounds}] GPT Call ==\n"
                    f"**System**:\n{system_content}\n\n"
                    f"**User**:\n{user_content}\n"
                )
                self._append_planner_log(log_text)

                if "gpt" in self.model_name.lower() or "gemini" in self.model_name.lower():
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=0,
                        n=1,
                    )
                    content = response.choices[0].message.content
                else:
                    response = self.client.chat.completions.create(
                        model=self.client.models.list().data[0].id,
                        messages=messages,
                        max_tokens=8192,
                        temperature=0,
                        n=1,
                    )
                    content = response.choices[0].message.content

                # 把 GPT 的原始返回写到日志
                response_str = json.dumps({
                    "role": "assistant",
                    "content": content
                }, ensure_ascii=False, indent=2)
                self._append_planner_log(f"**Raw Response**:\n{response_str}\n")

                return content

            except Exception as e:
                err_msg = f"[Planner] GPT plan generation error: {e}"
                self._append_planner_log(err_msg)
                time.sleep(5)
                if rounds > 3:
                    raise Exception(f"[Planner] GPT plan call failed too many times: {e}")
    
    def plan(self, status_text: str) -> str:
        prompt_path = "./planner_prompt.yaml"
        try:
            with open(prompt_path, "r", encoding="utf-8") as pf:
                prompt_data = yaml.safe_load(pf)
        except Exception as e:
            raise ValueError(f"[BasePlanner] Error reading prompt YAML from {prompt_path}: {e}")

        system_prompt_template = prompt_data.get("system", "")
        user_prompt_template = prompt_data.get("user", "")

        system_prompt = system_prompt_template.replace("<<tool description>>", self.tools_description)
        user_prompt = user_prompt_template.replace("<<status>>", status_text)

        if self.main_agent and hasattr(self.main_agent, '_build_tool_call_history'):
            tool_call_history_str = self.main_agent._build_tool_call_history(num=7)
            user_prompt += f"\n\nRecent Detailed Tool Calls:\n{tool_call_history_str}"
            user_prompt = user_prompt.replace("<<recent_tool_calls>>", tool_call_history_str)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ]
        planner_output = self.gpt_planner_call(messages)
        self._append_planner_log(f"=== Planner Plan Output ===\n{planner_output}")
        
        return planner_output
