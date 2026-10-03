import json
import re
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
        "source": _clean_value(product.get("source")),
        "source_url": _clean_value(product.get("source_url")),
    }

def _is_real_live_record(record):
    source_type = str(record.get("source_type", "")).lower()
    source = str(record.get("source", "")).lower()
    return source_type == "live_web" and source not in {"demo", "demonstration"}

def _attach_source_links(products, compact):
    """Attach only URLs actually supplied by retrieved evidence."""
    enriched = []
    for product in products:
        name = product.get("name", "").casefold()
        name_tokens = set(re.findall(r"[a-z0-9]+", name))
        links = []
        seen = set()
        for record in compact:
            title = record.get("title", "").casefold()
            title_tokens = set(re.findall(r"[a-z0-9]+", title))
            if not name or not title:
                continue
            if name in title or title in name or len(name_tokens & title_tokens) >= 2:
                url = record.get("url", "")
                if url and url not in seen:
                    links.append({"source": record.get("source", "Source"), "url": url})
                    seen.add(url)
        supplied = product.get("source_url", "")
        exact = next((x for x in links if x["url"] == supplied), None)
        if exact:
            links = [exact] + [x for x in links if x["url"] != supplied]
        product["availability"] = links
        product["source"] = links[0]["source"] if links else "Source not available"
        product["source_url"] = links[0]["url"] if links else ""
        enriched.append(product)
    return enriched

def build_comparison(query, structured, evidence):
    if not evidence:
        return []

    # Use the original source records preserved by the Evidence Agent.
    # This keeps real marketplace names and URLs available downstream.
    source_records = evidence.get("evidence_records", []) if isinstance(evidence, dict) else evidence

    # Only live-web records can become purchasable comparison products.
    # Knowledge-base and demonstration records are never treated as real products.
    compact = []
    seen = set()

    for item in source_records:
        if not isinstance(item, dict) or not _is_real_live_record({
            "source_type": item.get("source_type"),
            "source": item.get("source"),
        }):
            continue

        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        record = {
            "title": str(metadata.get("title") or item.get("source", "Product"))[:120],
            "source": str(item.get("source", "Unknown")),
            "price": str(item.get("price", "not extracted")),
            "specs": metadata.get("specs", {}),
            "evidence": str(item.get("text", ""))[:180],
            "url": str(metadata.get("url", "")),
        }

        key = (record["source"], record["title"], record["price"])
        if key in seen:
            continue
        seen.add(key)
        compact.append(record)

        if len(compact) >= 15:
            break

    raw = chat(
        COMPARISON_PROMPT,
        f"Request: {query}\n"
        f"Requirements: {json.dumps(structured, ensure_ascii=False)}\n"
        f"Evidence records: {json.dumps(compact, ensure_ascii=False)}"
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

    return _attach_source_links(cleaned, compact)
