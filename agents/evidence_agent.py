import json
from core.llm import chat
from core.prompts import EVIDENCE_PROMPT

def verify_evidence(query, structured, evidence):
    context = "\n\n".join(
        f"[{i+1}] {e['text']}\nSource: {e['source']}\nType: {e['source_type']}"
        for i, e in enumerate(evidence)
    )
    raw = chat(EVIDENCE_PROMPT, f"Request: {query}\nStructured: {json.dumps(structured)}\nEvidence:\n{context or 'None'}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"verified_claims": [], "conflicts": ["Evidence validator returned an unstructured result."],
                "gaps": ["Evidence could not be fully validated."], "notes": []}
