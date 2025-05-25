from openai import OpenAI
import os
import base64
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)
from typing import List, Union

import openai

# FIXME Define global constant for structured models
OPENAI_STRUCTURED_MODELS = ['gpt-4o']


class ChatOpenAI():
    DEFAULT_SYSTEM_PROMPT = "You are a helpful, creative, and smart assistant."

    def __init__(
        self,
        model_string="gpt-4o",
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        is_multimodal: bool=False,
        **kwargs):
        """
        :param model_string:
        :param system_prompt:
        :param is_multimodal:
        """
        self.system_prompt = system_prompt
        if os.getenv("OPENAI_API_KEY") is None:
            raise ValueError("Please set the OPENAI_API_KEY environment variable if you'd like to use OpenAI models.")
        
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
        )
        self.model_string = model_string
        self.is_multimodal = is_multimodal
    

    @retry(wait=wait_random_exponential(min=1, max=5), stop=stop_after_attempt(5))
    def generate(self, content: Union[str, List[Union[str, bytes]]], system_prompt=None, **kwargs):
        try:
            # Print retry attempt information
            attempt_number = self.generate.retry.statistics.get('attempt_number', 0) + 1
            if attempt_number > 1:
                print(f"Attempt {attempt_number} of 5")

            if isinstance(content, str):
                return self._generate_text(content, system_prompt=system_prompt, **kwargs)
            
            elif isinstance(content, list):
                if (not self.is_multimodal):
                    raise NotImplementedError("Multimodal generation is only supported for GPT-4 models.")
                
                return self._generate_multimodal(content, system_prompt=system_prompt, **kwargs)

        except openai.LengthFinishReasonError as e:
            print(f"Token limit exceeded: {str(e)}")
            print(f"Tokens used - Completion: {e.completion.usage.completion_tokens}, Prompt: {e.completion.usage.prompt_tokens}, Total: {e.completion.usage.total_tokens}")
            return {
                "error": "token_limit_exceeded",
                "message": str(e),
                "details": {
                    "completion_tokens": e.completion.usage.completion_tokens,
                    "prompt_tokens": e.completion.usage.prompt_tokens,
                    "total_tokens": e.completion.usage.total_tokens
                }
            }
        except openai.RateLimitError as e:
            print(f"Rate limit error encountered: {str(e)}")
            return {
                "error": "rate_limit",
                "message": str(e),
                "details": getattr(e, 'args', None)
            }
        except Exception as e:
            print(f"Error in generate method: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            print(f"Error details: {e.args}")
            return {
                "error": type(e).__name__,
                "message": str(e),
                "details": getattr(e, 'args', None)
            }
        
    def _generate_text(
        self, prompt, system_prompt=None, temperature=0, max_tokens=4000, top_p=0.99, response_format=None
    ):

        sys_prompt_arg = system_prompt if system_prompt else self.system_prompt

        if self.model_string in ['o1', 'o1-mini']: # only supports base response currently
            response = self.client.beta.chat.completions.parse(
                model=self.model_string,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=max_tokens
            )
            if response.choices[0].finishreason == "length":
                response = "Token limit exceeded"
            else:
                response = response.choices[0].message.parsed
        elif self.model_string in OPENAI_STRUCTURED_MODELS and response_format is not None:
            response = self.client.beta.chat.completions.parse(
                model=self.model_string,
                messages=[
                    {"role": "system", "content": sys_prompt_arg},
                    {"role": "user", "content": prompt},
                ],
                frequency_penalty=0,
                presence_penalty=0,
                stop=None,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                response_format=response_format
            )
            response = response.choices[0].message.parsed
        else:
            response = self.client.chat.completions.create(
                model=self.model_string,
                messages=[
                    {"role": "system", "content": sys_prompt_arg},
                    {"role": "user", "content": prompt},
                ],
                frequency_penalty=0,
                presence_penalty=0,
                stop=None,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )
            response = response.choices[0].message.content
        return response

    def __call__(self, prompt, **kwargs):
        return self.generate(prompt, **kwargs)

    def _format_content(self, content: List[Union[str, bytes]]) -> List[dict]:
        formatted_content = []
        for item in content:
            if isinstance(item, bytes):
                base64_image = base64.b64encode(item).decode('utf-8')
                formatted_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                })
            elif isinstance(item, str):
                formatted_content.append({
                    "type": "text",
                    "text": item
                })
            else:
                raise ValueError(f"Unsupported input type: {type(item)}")
        return formatted_content

    def _generate_multimodal(
        self, content: List[Union[str, bytes]], system_prompt=None, temperature=0, max_tokens=4000, top_p=0.99, response_format=None
    ):
        sys_prompt_arg = system_prompt if system_prompt else self.system_prompt
        formatted_content = self._format_content(content)

        if self.model_string in ['o1', 'o1-mini']: # only supports base response currently
            print(f'Max tokens: {max_tokens}')
            response = self.client.chat.completions.create(
                model=self.model_string,
                messages=[
                    {"role": "user", "content": formatted_content},
                ],
                max_completion_tokens=max_tokens
            )
            if response.choices[0].finish_reason == "length":
                response_text = "Token limit exceeded"
            else:
                response_text = response.choices[0].message.content
        elif self.model_string in OPENAI_STRUCTURED_MODELS and response_format is not None:
            response = self.client.beta.chat.completions.parse(
                model=self.model_string,
                messages=[
                    {"role": "system", "content": sys_prompt_arg},
                    {"role": "user", "content": formatted_content},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                response_format=response_format
            )
            response_text = response.choices[0].message.parsed
        else:
            response = self.client.chat.completions.create(
                model=self.model_string,
                messages=[
                    {"role": "system", "content": sys_prompt_arg},
                    {"role": "user", "content": formatted_content},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )
            response_text = response.choices[0].message.content
        return response_text