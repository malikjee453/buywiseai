import json
import re
from core.llm import chat
from core.prompts import QUERY_ANALYZER_PROMPT


def _fallback_analysis(query, category="", budget="", language="English"):
    """Keep research usable when the LLM endpoint is temporarily blocked."""
    q = str(query or "").strip().lower()
    detected_category = str(category or "").strip()

    if not detected_category:
        if any(term in q for term in ("phone", "smartphone", "mobile", "iphone", "galaxy", "redmi")):
            detected_category = "Smartphone"
        elif any(term in q for term in ("laptop", "macbook", "thinkpad", "notebook")):
            detected_category = "Laptop"
        elif any(term in q for term in ("fridge", "refrigerator", "washing machine", "microwave", "air conditioner")):
            detected_category = "Appliance"
        elif any(term in q for term in ("shirt", "dress", "kurta", "lawn", "skirt", "skirts", "shoe", "sandal")):
            detected_category = "Fashion"
        else:
            detected_category = "Electronics"

    budget_text = str(budget or "").strip()
    if not budget_text:
        match = re.search(
            r"(?:under|below|less than|upto|up to|budget)\D{0,20}(?:PKR|Rs\.?|)\s*([0-9][0-9,]*)",
            str(query or ""),
            re.I,
        )
        if match:
            budget_text = f"PKR {match.group(1)}"

    return {
        "category": detected_category,
        "budget": budget_text,
        "currency": "PKR" if ("pkr" in q or "rs" in q or "rupee" in q) else "",
        "use_case": "",
        "requirements": [],
        "comparison_intent": True,
        "language": language or "English",
    }


def analyze_query(query, category="", budget="", language="English"):
    try:
        raw = chat(
            QUERY_ANALYZER_PROMPT,
            f"""User query: {query}
Category: {category or "not supplied"}
Budget: {budget or "not supplied"}
Language: {language}

Return JSON with category, budget, currency, use_case, requirements,
comparison_intent, and language.""",
        )
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return _fallback_analysis(query, category, budget, language)
    except Exception:
        return _fallback_analysis(query, category, budget, language)
