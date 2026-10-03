from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

class ProductQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")
    original_query: str = Field(min_length=1, max_length=500)
    normalized_query: str = Field(min_length=1, max_length=500)
    product_name: Optional[str] = None
    brand: Optional[str] = None
    specs: list[str] = Field(default_factory=list)
    min_price: Optional[float] = Field(default=None, ge=0)
    max_price: Optional[float] = Field(default=None, ge=0)
    country: str = "Pakistan"
    currency: str = "PKR"
    query_variants: list[str] = Field(default_factory=list)

    @field_validator("normalized_query")
    @classmethod
    def normalize_whitespace(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("max_price")
    @classmethod
    def max_must_not_be_below_min(cls, value, info):
        minimum = info.data.get("min_price")
        if value is not None and minimum is not None and value < minimum:
            raise ValueError("max_price cannot be lower than min_price")
        return value

class RawSearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = ""
    url: str = ""
    snippet: str = ""
    source: str = ""
    price_text: Optional[str] = None
    merchant: Optional[str] = None
    rating_text: Optional[str] = None
    provider: str = ""
    raw_data: dict = Field(default_factory=dict)

class ProductListing(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=1)
    price: float = Field(gt=0)
    currency: str = Field(min_length=1, max_length=8)
    source: str = Field(min_length=1)
    url: HttpUrl
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    availability: Optional[str] = None
    snippet: Optional[str] = None
    verified: bool = False
    verification_note: Optional[str] = None
    possible_scam: bool = False
    normalized_price: Optional[float] = Field(default=None, gt=0)

class SearchState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    query: Optional[ProductQuery] = None
    raw_results: list[RawSearchResult] = Field(default_factory=list)
    listings: list[ProductListing] = Field(default_factory=list)
    verified_listings: list[ProductListing] = Field(default_factory=list)
    search_round: int = 0
    trace: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
