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

    title = re.sub(r"\s+", " ", title).strip()

    # Remove common retailer snippet clutter while keeping the product name
    # exactly grounded in the retrieved title.
    title = re.sub(
        r"^\d+(?:\.\d+)?\s+\d+\s+Reviews?\s+",
        "",
        title,
        flags=re.I,
    )
    title = re.sub(
        r"\s+Rs\s+[\d,]+(?:\s+Rs\s+[\d,]+)?\s+\d+%\s+OFF.*$",
        "",
        title,
        flags=re.I,
    )
    title = re.sub(
        r"\s+PKR\s+[\d,]+.*$",
        "",
        title,
        flags=re.I,
    )

    return title.strip()[:120] or _clean(source, "Product")


def _record_to_product(item):
    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    url = _clean(metadata.get("url"), "")
    source = _clean(item.get("source"), "")
    if not url or not source:
        return None

    specs = metadata.get("specs")
    if not isinstance(specs, dict):
        specs = {}

    return {
        "name": _display_name(metadata, source),
        "price": _clean(item.get("price")),
        "key_specs": {
            "display": _clean(specs.get("display")),
            "performance": "Not available in evidence",
            "battery": _clean(specs.get("battery")),
            "camera": _clean(specs.get("camera")),
            "storage_ram": _clean(
                " / ".join(
                    value for value in (
                        _clean(specs.get("storage"), ""),
                        _clean(specs.get("ram"), ""),
                    )
                    if value
                ),
                "Not available in evidence",
            ),
        },
        "strengths": [],
        "tradeoffs": [],
        "requirement_fit": [],
        "evidence_status": "Retrieved from live web evidence",
        "source": source,
        "source_url": url,
        "availability": [{"source": source, "url": url}],
    }


def build_comparison(query, structured, evidence):
    """
    Build the buyer-facing table deterministically from verified live records.

    The previous version sent all candidate products to the LLM and asked it
    to choose the output. That allowed the model to return only 3 products
    even when 10+ live records had been retrieved, and it could also hit the
    Groq token limit. The buyer table must preserve retrieved products exactly,
    so no LLM selection is needed here.
    """
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

        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        url = str(metadata.get("url", "")).strip()
        if not url or url in seen_urls:
            continue

        product = _record_to_product(item)
        if not product:
            continue

        seen_urls.add(url)
        candidates.append(product)

    # Preserve source diversity: take up to 3 products from each source first.
    # Then fill remaining slots from unused products. This targets 12 products
    # while never fabricating a source or URL.
    selected = []
    selected_urls = set()
    source_counts = {}

    for product in candidates:
        source = product["source"]
        if source_counts.get(source, 0) >= 3:
            continue
        selected.append(product)
        selected_urls.add(product["source_url"])
        source_counts[source] = source_counts.get(source, 0) + 1
        if len(selected) >= 12:
            break

    if len(selected) < 12:
        for product in candidates:
            if product["source_url"] in selected_urls:
                continue
            selected.append(product)
            selected_urls.add(product["source_url"])
            if len(selected) >= 12:
                break

    return selected
