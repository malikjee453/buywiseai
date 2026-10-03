import pytest
from pydantic import ValidationError
from buywise.schemas import ProductListing, ProductQuery

def test_query_normalizes_whitespace():
    q = ProductQuery(original_query="  iPhone   15  ", normalized_query="  iPhone   15  ")
    assert q.normalized_query == "iPhone 15"

def test_query_rejects_bad_range():
    with pytest.raises(ValidationError):
        ProductQuery(original_query="shoes", normalized_query="shoes", min_price=100, max_price=50)

def test_listing_requires_positive_price():
    with pytest.raises(ValidationError):
        ProductListing(title="x", price=0, currency="PKR", source="Example", url="https://example.com/x")

def test_listing_accepts_url():
    x = ProductListing(title="x", price=100, currency="PKR", source="Example", url="https://example.com/x")
    assert str(x.url) == "https://example.com/x"
