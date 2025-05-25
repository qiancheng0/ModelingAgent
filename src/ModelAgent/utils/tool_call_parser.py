import json, re, uuid
from types import SimpleNamespace
from typing import Any, List

PYTHON_TAG_RE = re.compile(r"<\|python_tag\|>\s*(\{.*?})", re.S)
JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?})\s*```", re.S | re.I)

def _to_dict(obj: Any) -> dict:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return obj
    return {"content": str(obj)}

def _to_ns(d: dict) -> SimpleNamespace:
    """Convert True/False/None to valid JSON; remove trailing commas and other common issues"""
    if isinstance(d, dict):
        return SimpleNamespace(**{k: _to_ns(v) for k, v in d.items()})
    if isinstance(d, list):
        return [_to_ns(i) for i in d]
    return d

def _fix_json(text: str) -> str:
    rep = [
        (r"\bTrue\b",  "true"),
        (r"\bFalse\b", "false"),
        (r"\bNone\b",  "null"),
        (r",\s*([}\]])", r"\1")
    ]
    for pat, repl in rep:
        text = re.sub(pat, repl, text)
    return text

def _build_tool_call(name: str, arguments: dict, call_id: str | None = None):
    return {
        "id": call_id or f"call_{uuid.uuid4().hex[:8]}",
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments, ensure_ascii=False)
        }
    }

def extract_tool_call(message: Any):
    """
    Parse assistant message, return *new* SimpleNamespace:
    - If already contains function_call/tool_calls → directly normalize and return
    - Otherwise try to parse <|python_tag|> / ```json``` code blocks from content
    - If both fail ⇒ return original message
    """
    msg_dict = _to_dict(message)

    if fc := msg_dict.get("function_call"):
        tool = _build_tool_call(fc.get("name"), json.loads(fc.get("arguments", "{}")))
        return _to_ns({"role": "assistant", "content": None, "tool_calls": [tool]})

    if msg_dict.get("tool_calls"):
        return _to_ns(msg_dict)

    content: str = msg_dict.get("content") or ""
    if not content:
        return message

    match = PYTHON_TAG_RE.search(content)
    if not match:
        match = JSON_BLOCK_RE.search(content)
    if not match:
        return message
    
    json_txt = _fix_json(match.group(1).strip())
    try:
        payload = json.loads(json_txt)
    except json.JSONDecodeError:
        return message 

    # Allow payload to be directly a list/single item
    calls: List[dict] = []
    if isinstance(payload, list):
        for p in payload:
            calls.append(
                _build_tool_call(p.get("name"), p.get("parameters", {}), p.get("id"))
            )
    else:
        calls.append(
            _build_tool_call(payload.get("name"),
                             payload.get("parameters", {}),
                             payload.get("id"))
        )

    return _to_ns({"role": "assistant", "content": None, "tool_calls": calls})