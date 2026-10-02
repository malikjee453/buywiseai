import json
from core.llm import chat
from core.prompts import QUERY_ANALYZER_PROMPT

def analyze_query(query, category="", budget="", language="English"):
    raw = chat(QUERY_ANALYZER_PROMPT, f'''
User query: {query}
Category: {category or "not supplied"}
Budget: {budget or "not supplied"}
Language: {language}

Return JSON with category, budget, currency, use_case, requirements,
comparison_intent, and language.
''')
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"category": category, "budget": budget, "currency": "",
                "use_case": "", "requirements": [], "comparison_intent": False,
                "language": language}
