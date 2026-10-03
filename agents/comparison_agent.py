import re


def _is_real_live_record(record):
    source_type = str(record.get("source_type", "")).lower()
    source = str(record.get("source", "")).lower()
    return source_type == "live_web" and source not in {"demo", "demonstration"}


def _clean(value, fallback="Not available in evidence"):
    if value is None:
        return fallback
    value = str(value).strip()
    return value or fallback


def _display_name(metadata, source):
    title = _clean(metadata.get("title"), "")
    if not title:
        return _clean(source, "Product")
    title = re.sub(r"\\s+", " ", title).strip()
    title = re.sub(r"^\\d+(?:\\.\\d+)?\\s+\\d+\\s+Reviews?\\s+", "", title, flags=re.I)
    title = re.sub(r"\\s+Rs\\s+[\\d,]+(?:\\s+Rs\\s+[\\d,]+)?\\s+\\d+%\\s+OFF.*$", "", title, flags=re.I)
    title = re.sub(r"\\s+PKR\\s+[\\d,]+.*$", "", title, flags=re.I)
    return title.strip()[:120] or _clean(source, "Product")


def _record_to_product(item):
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    url = _clean(metadata.get("url"), "")
    source = _clean(item.get("source"), "")
    if not url or not source:
        return None
    specs = metadata.get("specs") if isinstance(metadata.get("specs"), dict) else {}
    verification = metadata.get("verification") if isinstance(metadata.get("verification"), dict) else {}
    checks = verification.get("checks") if isinstance(verification.get("checks"), dict) else {}
    price_verified = bool(verification.get("price_verified"))
    specs_verified = bool(verification.get("specs_verified"))
    status = str(verification.get("status", "insufficient"))

    return {
        "name": _display_name(metadata, source),
        "price": _clean(item.get("price")),
        "key_specs": {
            "display": _clean(specs.get("display")),
            "performance": "Not available in evidence",
            "battery": _clean(specs.get("battery")),
            "camera": _clean(specs.get("camera")),
            "storage_ram": _clean(" / ".join(value for value in (_clean(specs.get("storage"), ""), _clean(specs.get("ram"), "")) if value), "Not available in evidence"),
        },
        "verification": {
            "status": status,
            "price_verified": price_verified,
            "specs_verified": specs_verified,
            "variant_identified": bool(checks.get("variant_identified")),
        },
        "evidence_status": status,
        "source": source,
        "source_url": url,
        "availability": [{"source": source, "url": url}],
    }


def build_comparison(query, structured, evidence):
    if not isinstance(evidence, dict):
        return []
    source_records = evidence.get("evidence_records", [])
    if not isinstance(source_records, list):
        return []

    candidates = []
    seen_urls = set()
    for item in source_records:
        if not isinstance(item, dict) or not _is_real_live_record(item):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        url = str(metadata.get("url", "")).strip()
        if not url or url in seen_urls:
            continue
        product = _record_to_product(item)
        if product:
            seen_urls.add(url)
            candidates.append(product)

    by_source = {}
    for product in candidates:
        by_source.setdefault(product["source"], []).append(product)

    selected = []
    selected_urls = set()
    for round_index in range(3):
        for source, source_products in by_source.items():
            if round_index >= len(source_products):
                continue
            product = source_products[round_index]
            if product["source_url"] in selected_urls:
                continue
            selected.append(product)
            selected_urls.add(product["source_url"])
            if len(selected) >= 12:
                return selected
    return selected
