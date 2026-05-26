"""Helper utilities for workflow evaluation moved out of q2_workflow_ordering.py
"""
import json
import re
import uuid
from typing import Any, Dict


ORDINAL_WORDS = [
    "first", "second", "third", "fourth", "fifth",
    "then", "next", "finally", "last", "before", "after",
    "step"
]


def _scrub_text(text: str) -> str:
    """Remove obvious order hints from name/description."""
    t = re.sub(r"\bstep\s*\d+\b", "step", text, flags=re.I)
    t = re.sub(r"\b(" + "|".join(ORDINAL_WORDS) + r")\b", "", t, flags=re.I)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def _deep_replace_step_refs(obj: Any, id_mapping: Dict[str, str]) -> Any:
    """
    Recursively replace {{step_<old>...}} to {{step_<new>...}} in strings.
    """
    if isinstance(obj, dict):
        return {k: _deep_replace_step_refs(v, id_mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_replace_step_refs(x, id_mapping) for x in obj]
    if isinstance(obj, str):
        def repl(m):
            old = m.group(2)      # step_id
            new = id_mapping.get(old, old)
            return "{{" + prefix + "step_" + new + tail + suffix + "}}"
        
        return re.sub(r"\{\{(\s*)step_(\w+)([^}]*)(\s*)\}\}", repl, obj)
    return obj


def obfuscate_steps(steps: list) -> Dict[str, str]:
    """
    Assign non-sequential IDs (short UUID), update dependencies and template refs,
    and scrub order-hint words in names/descriptions.
    Returns: id_mapping {old_id -> new_id}
    """
    new_ids = [uuid.uuid4().hex[:8] for _ in steps]
    id_mapping = {step['step_id']: new_ids[i] for i, step in enumerate(steps)}

    for step in steps:
        old = step['step_id']
        step['step_id'] = id_mapping[old]

    for step in steps:
        # Update steps
        if 'next_steps' in step and isinstance(step['next_steps'], list):
            step['next_steps'] = [id_mapping.get(x, x) for x in step['next_steps']]
        if 'else_steps' in step and isinstance(step.get('else_steps'), list):
            step['else_steps'] = [id_mapping.get(x, x) for x in step['else_steps']]
        if 'error_handler' in step and step.get('error_handler'):
            step['error_handler'] = id_mapping.get(step['error_handler'], step['error_handler'])

        # Replace template refs in parameters or any fields
        for key in list(step.keys()):
            step[key] = _deep_replace_step_refs(step[key], id_mapping)

        # Scrub names/descriptions
        if isinstance(step.get('name'), str):
            step['name'] = _scrub_text(step['name'])
        if isinstance(step.get('description'), str):
            step['description'] = _scrub_text(step['description'])

        # Replace step IDs in the 'condition' field if present
        if 'condition' in step and isinstance(step['condition'], dict):
            step['condition'] = _deep_replace_step_refs(step['condition'], id_mapping)
        
        # Replace step IDs in the 'parameters' field if present
        if 'parameters' in step and isinstance(step['parameters'], dict):
            step['parameters'] = _deep_replace_step_refs(step['parameters'], id_mapping)
            
    return id_mapping


def parse_llm_output(text: str) -> Dict:
    text = text.strip()

    fence_match = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    else:
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict) and 'workflow_steps' in data:
            return data
    except json.JSONDecodeError:
        pass

    start = None
    for i, ch in enumerate(text):
        if ch in '{[':
            start = i
            break

    if start is None:
        raise ValueError("No JSON found in LLM output")

    stack, in_string, esc = [], False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == '{':
                stack.append('{')
            elif ch == '[':
                stack.append('[')
            elif ch == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
            elif ch == ']':
                if stack and stack[-1] == '[':
                    stack.pop()

            if not stack and i > start:
                payload = text[start:i+1]
                try:
                    data = json.loads(payload)
                    if isinstance(data, dict) and 'workflow_steps' in data:
                        return data
                except json.JSONDecodeError:
                    pass
                break

    payload = text[start:]
    if payload.startswith('{'):
        m = re.search(r'"workflow_steps"\s*:\s*\[', payload)
        if m:
            arr_start = m.end()
            steps = []
            i = arr_start
            while i < len(payload):
                # skip whitespace + commas
                while i < len(payload) and payload[i] in ' \t\n\r,':
                    i += 1
                if i >= len(payload) or payload[i] != '{':
                    break
                # try to parse one step object
                depth = 0; j = i; in_str = False; esc2 = False
                while j < len(payload):
                    c = payload[j]
                    if in_str:
                        if esc2: esc2 = False
                        elif c == '\\': esc2 = True
                        elif c == '"': in_str = False
                    else:
                        if c == '"': in_str = True
                        elif c == '{': depth += 1
                        elif c == '}':
                            depth -= 1
                            if depth == 0:
                                try:
                                    step = json.loads(payload[i:j+1])
                                    steps.append(step)
                                except json.JSONDecodeError:
                                    pass
                                i = j + 1
                                break
                    j += 1
                else:
                    # incomplete last step — stop
                    break
            if steps:
                return {"workflow_steps": steps}

    raise ValueError("Failed to extract valid workflow JSON")
