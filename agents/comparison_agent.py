import json
from core.llm import chat
from core.prompts import COMPARISON_PROMPT

def build_comparison(query, structured, evidence):
    raw = chat(COMPARISON_PROMPT, f"Request: {query}\nRequirements: {json.dumps(structured)}\nEvidence: {json.dumps(evidence)}")
    try:
        return json.loads(raw).get("products", [])
    except json.JSONDecodeError:
        return []
