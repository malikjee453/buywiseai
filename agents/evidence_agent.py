import json
import re
from core.llm import chat
from core.prompts import EVIDENCE_PROMPT

MAX_EVIDENCE_ITEMS = 10
MAX_TEXT_CHARS = 420

def _normalize_price(value):
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    return int(digits) if digits else None

def _compact_evidence(evidence):
    compact = []
    seen = set()

    for item in evidence:
        if not isinstance(item, dict):
            continue

        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        specs = metadata.get("specs", {})
        if not isinstance(specs, dict):
            specs = {}

        source = str(item.get("source", "Unknown"))
        title = str(metadata.get("title") or source)
        price = item.get("price", "not extracted")
        text = str(item.get("text", ""))[:MAX_TEXT_CHARS]

        key = (source, title, str(price))
        if key in seen:
            continue
        seen.add(key)

        compact.append({
            "title": title[:120],
            "source": source,
            "source_type": item.get("source_type", "unknown"),
            "price": str(price),
            "specs": specs,
            "evidence": text,
        })

        if len(compact) >= MAX_EVIDENCE_ITEMS:
            break

    return compact

def _local_checks(evidence):
    notes = []
    conflicts = []
    gaps = []

    if not evidence:
        gaps.append("No external or knowledge-base evidence was retrieved.")
        return notes, conflicts, gaps

    priced = []
    sources = set()

    for item in evidence:
        source = item.get("source", "Unknown")
        sources.add(source)
        price = _normalize_price(item.get("price"))
        if price is not None:
            priced.append((price, source))

    if len(sources) == 1:
        notes.append("Evidence currently comes from one source; independent confirmation is recommended.")

    if len(priced) >= 2:
        values = {p for p, _ in priced}
        if len(values) > 1:
            conflicts.append(
                "Different retrieved records contain different prices; treat price as time-sensitive and verify before purchase."
            )

    return notes, conflicts, gaps

def verify_evidence(query, structured, evidence):
    compact = _compact_evidence(evidence)
    local_notes, local_conflicts, local_gaps = _local_checks(evidence)

    context = json.dumps(compact, ensure_ascii=False)

    raw = chat(
        EVIDENCE_PROMPT,
        f"Request: {query}\n"
        f"Structured: {json.dumps(structured, ensure_ascii=False)}\n"
        f"Evidence records:\n{context or 'None'}"
    )

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {
            "verified_claims": [],
            "conflicts": [],
            "gaps": [],
            "notes": []
        }

    result.setdefault("verified_claims", [])
    result.setdefault("conflicts", [])
    result.setdefault("gaps", [])
    result.setdefault("notes", [])

    def _clean_messages(values):
        cleaned = []
        seen = set()
        if not isinstance(values, list):
            values = [values]
        for value in values:
            if isinstance(value, dict):
                value = value.get("message") or value.get("text") or json.dumps(value, ensure_ascii=False)
            value = str(value).strip()
            if value and value not in seen:
                seen.add(value)
                cleaned.append(value)
        return cleaned

    result["notes"] = _clean_messages(result["notes"] + local_notes)
    result["conflicts"] = _clean_messages(result["conflicts"] + local_conflicts)
    result["gaps"] = _clean_messages(result["gaps"] + local_gaps)

    if result["conflicts"]:
        result["status"] = "conflicting"
    elif result["gaps"]:
        result["status"] = "uncertain"
    elif result["verified_claims"]:
        result["status"] = "supported"
    else:
        result["status"] = "insufficient"

    return result
