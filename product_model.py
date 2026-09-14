from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class ProductData(BaseModel):
    """Validated product information returned by the scraper."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_url: HttpUrl
    product_name: Optional[str] = Field(default=None, max_length=300)
    price: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=4000)
    review_rating: Optional[float] = Field(default=None, ge=0, le=5)

    @field_validator("product_name", "price", "description", mode="before")
    @classmethod
    def empty_strings_become_none(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("review_rating", mode="before")
    @classmethod
    def normalize_rating(cls, value):
        if value in (None, ""):
            return None
        try:
            rating = float(value)
        except (TypeError, ValueError):
            return None
        if 0 <= rating <= 5:
            return rating
        return None
