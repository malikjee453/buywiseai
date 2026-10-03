from buywise.providers.common import (
    is_relevant_product,
    normalize_url,
    parse_price,
    raw_to_listing,
)
from buywise.schemas import RawSearchResult


def test_parse_price_requires_currency():
    assert parse_price("5000 reviews", "rating 4.8") is None


def test_parse_price_supports_common_currencies():
    assert parse_price("Rs 77,249", "") == (77249.0, "PKR")
    assert parse_price("$799.99", "") == (799.99, "USD")


def test_normalize_url_removes_tracking():
    url = "https://Example.com/product/123?utm_source=x&gclid=abc&color=black#reviews"
    assert normalize_url(url) == "https://example.com/product/123?color=black"


def test_raw_to_listing_rejects_missing_price():
    raw = RawSearchResult(
        title="Example product",
        url="https://example.com/product/1",
        snippet="Rated 4.8 from 500 reviews",
        source="Example",
        provider="test",
    )
    assert raw_to_listing(raw) is None


def test_raw_to_listing_accepts_real_price():
    raw = RawSearchResult(
        title="Example phone iPhone 15 128GB",
        url="https://example.com/product/1?utm_source=test",
        snippet="Rs 77,249",
        source="Example",
        provider="test",
    )
    listing = raw_to_listing(raw)
    assert listing is not None
    assert listing.price == 77249.0
    assert listing.currency == "PKR"
    assert str(listing.url) == "https://example.com/product/1"


def test_relevance_rejects_wrong_storage():
    raw = RawSearchResult(
        title="Apple iPhone 15 256GB",
        url="https://example.com/product/1",
        snippet="Rs 284,000",
        source="Example",
        provider="test",
    )
    assert is_relevant_product("iPhone 15 128GB", raw)[0] is False


def test_relevance_accepts_exact_storage():
    raw = RawSearchResult(
        title="Apple iPhone 15 128GB Black",
        url="https://example.com/product/1",
        snippet="Rs 284,000",
        source="Example",
        provider="test",
    )
    assert is_relevant_product("iPhone 15 128GB", raw)[0] is True
