import json
from core.llm import chat
from core.prompts import COMPARISON_PROMPT

REQUIRED_FIELDS = (
    "display",
    "performance",
    "battery",
    "camera",
    "storage_ram",
)

def _clean_value(value):
    if value is None:
        return "Not available in evidence"
    value = str(value).strip()
    return value or "Not available in evidence"

def _normalize_product(product):
    if not isinstance(product, dict):
        return None

    name = _clean_value(product.get("name"))
    if name == "Not available in evidence":
        return None

    specs = product.get("key_specs")
    if not isinstance(specs, dict):
        specs = {}

    strengths = product.get("strengths")
    tradeoffs = product.get("tradeoffs")
    fit = product.get("requirement_fit")

    return {
        "name": name,
        "price": _clean_value(product.get("price")),
        "key_specs": {
            field: _clean_value(specs.get(field))
            for field in REQUIRED_FIELDS
        },
        "strengths": (
            [str(x).strip() for x in strengths if str(x).strip()]
            if isinstance(strengths, list) else []
        ),
        "tradeoffs": (
            [str(x).strip() for x in tradeoffs if str(x).strip()]
            if isinstance(tradeoffs, list) else []
        ),
        "requirement_fit": (
            [str(x).strip() for x in fit if str(x).strip()]
            if isinstance(fit, list) else []
        ),
        "evidence_status": _clean_value(product.get("evidence_status")),
    }

def build_comparison(query, structured, evidence):
    if not evidence:
        return []

    raw = chat(
        COMPARISON_PROMPT,
        f"Request: {query}\n"
        f"Requirements: {json.dumps(structured, ensure_ascii=False)}\n"
        f"Evidence: {json.dumps(evidence, ensure_ascii=False)}"
    )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    products = data.get("products", [])
    if not isinstance(products, list):
        return []

    cleaned = []
    seen = set()

    for product in products:
        normalized = _normalize_product(product)
        if not normalized:
            continue

        key = normalized["name"].casefold()
        if key in seen:
            continue

        seen.add(key)
        cleaned.append(normalized)

    return cleaned
