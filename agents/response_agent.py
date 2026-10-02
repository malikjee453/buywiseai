import json
from core.llm import chat
from core.prompts import RESPONSE_PROMPT

def generate_response(query, structured, evidence, comparison, language):
    return chat(RESPONSE_PROMPT, f"User request: {query}\nLanguage: {language}\nStructured: {json.dumps(structured)}\nEvidence: {json.dumps(evidence)}\nComparison: {json.dumps(comparison)}")
