import re


def money(value):
    digits = re.sub(r"\\D", "", str(value or ""))
    return int(digits) if digits else None


def validate_record(record):
    """Attach transparent validation metadata; never invent missing facts."""
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    specs = metadata.get("specs") if isinstance(metadata.get("specs"), dict) else {}
    title = str(metadata.get("title", "")).strip()
    url = str(metadata.get("url", "")).strip()
    price = money(record.get("price"))
    currency = str(metadata.get("currency", "")).upper()

    checks = {
        "product_url": bool(url and url.startswith("http")),
        "title": len(title) >= 3,
        "price": bool(price and price >= 1000),
    }

    # A price is considered source-verified only when the extractor explicitly
    # marked it as coming from structured Product/Offer data on the detail page.
    price_source = str(metadata.get("price_source", "")).lower()
    checks["price_verified"] = price_source == "jsonld_product_offer"

    variant = str(metadata.get("variant", "")).strip()
    checks["variant_identified"] = bool(variant)

    # These are facts actually extracted from the product page. Missing values
    # remain missing; validation never fills them from model knowledge.
    spec_count = sum(bool(str(v).strip()) for v in specs.values())
    checks["specs_present"] = spec_count > 0

    if checks["price_verified"] and checks["product_url"] and checks["title"]:
        status = "verified"
    elif checks["product_url"] and checks["title"] and checks["price"]:
        status = "partial"
    else:
        status = "insufficient"

    metadata["verification"] = {
        "status": status,
        "checks": checks,
        "price_verified": checks["price_verified"],
        "specs_verified": checks["specs_present"],
    }
    record["metadata"] = metadata
    return record


def verified_price(record):
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    verification = metadata.get("verification") if isinstance(metadata.get("verification"), dict) else {}
    return bool(verification.get("price_verified"))
