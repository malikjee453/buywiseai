import json
from core.llm import chat
from core.prompts import RESPONSE_PROMPT

def generate_response(query, structured, evidence, comparison, language):
    # Keep raw live records and URLs out of the response-model prompt.
    safe_evidence = {
        "verified_claims": evidence.get("verified_claims", [])[:6],
        "conflicts": evidence.get("conflicts", [])[:6],
        "gaps": evidence.get("gaps", [])[:6],
        "notes": evidence.get("notes", [])[:6],
        "status": evidence.get("status", "uncertain"),
    }
    return chat(
        RESPONSE_PROMPT,
        f"User request: {query}\n"
        f"Language: {language}\n"
        f"Structured: {json.dumps(structured, ensure_ascii=False)}\n"
        f"Evidence summary: {json.dumps(safe_evidence, ensure_ascii=False)}\n"
        f"Comparison: {json.dumps(comparison, ensure_ascii=False)}"
    )
