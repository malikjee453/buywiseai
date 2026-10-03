import re


def money(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else None


def validate_record(record):
    """Attach transparent validation metadata; never invent missing facts."""
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    specs = metadata.get("specs") if isinstance(metadata.get("specs"), dict) else {}
    title = str(metadata.get("title", "")).strip()
    url = str(metadata.get("url", "")).strip()
    price = money(record.get("price"))
    currency = str(metadata.get("currency", "")).upper()
    source = str(record.get("source", "")).strip()
    source_type = str(record.get("source_type", "")).strip().lower()

    checks = {
        "product_url": bool(url and url.startswith("http")),
        "title": len(title) >= 3,
        "price": bool(price and price >= 1000),
        "source": bool(source),
        "live_source": source_type == "live_web",
    }

    # Price evidence is verified when it was extracted from the exact product
    # page, either from structured Product/Offer data or visible page text.
    # Search/listing-page context alone is not enough.
    price_source = str(metadata.get("price_source", "")).lower()
    checks["price_verified"] = (
        price_source in {"jsonld_product_offer", "product_page_text"}
        and checks["product_url"]
        and checks["title"]
        and checks["price"]
        and checks["live_source"]
    )

    variant = str(metadata.get("variant", "")).strip()
    checks["variant_identified"] = bool(variant)

    # These are facts actually extracted from the product page. Missing values
    # remain missing; validation never fills them from model knowledge.
    spec_count = sum(bool(str(v).strip()) for v in specs.values())
    checks["specs_present"] = spec_count > 0

    # Full verification requires the exact live product page plus both price
    # and at least one relevant specification from that same page.
    if (
        checks["price_verified"]
        and checks["specs_present"]
        and checks["product_url"]
        and checks["title"]
        and checks["source"]
    ):
        status = "verified"
    elif (
        checks["product_url"]
        and checks["title"]
        and checks["price"]
        and checks["source"]
        and checks["live_source"]
    ):
        status = "partial"
    else:
        status = "insufficient"

    metadata["verification"] = {
        "status": status,
        "checks": checks,
        "price_verified": checks["price_verified"],
        "specs_verified": checks["specs_present"],
        "source_verified": checks["product_url"] and checks["source"] and checks["live_source"],
        "source": source,
        "source_url": url,
        "price_source": price_source or "not_available",
        "specs_source": "product_page" if checks["specs_present"] else "not_available",
    }
    record["metadata"] = metadata
    return record


def verified_price(record):
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    verification = metadata.get("verification") if isinstance(metadata.get("verification"), dict) else {}
    return bool(verification.get("price_verified"))
