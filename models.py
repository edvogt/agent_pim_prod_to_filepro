# ============================================================================
#  models.py — Pydantic Data Models
#  Version: 1.3.0
#  CHANGES: Added None handling for optional fields, improved HTML sanitization, web_price fallback to retail_price
# ============================================================================
from pydantic import BaseModel, Field
from typing import Optional
import html
import re

class PimcoreProduct(BaseModel):
    id: str
    sku: str
    upc: Optional[str] = None
    web_price: float = Field(0.0, alias="WebPrice")
    map_price: float = Field(0.0, alias="MAP")
    retail_price: float = Field(0.0, alias="Retail")
    brand_name: str = Field(..., alias="BrandName")
    model: Optional[str] = Field(None, alias="Model")
    vendor_part_number: str = Field(..., alias="VendorPartNumber")
    description_short: Optional[str] = Field("", alias="Description_Short")
    description_medium: Optional[str] = Field("", alias="Description_Medium")
    specifications_wysiwyg: Optional[str] = Field("", alias="Specifications_WYSIWYG")
    whats_in_box: Optional[str] = Field("", alias="WhatsInBox")
    product_type_raw: Optional[str] = Field(None, alias="ProductType")
    image_asset_id: Optional[str] = None

    @property
    def effective_web_price(self) -> float:
        """Returns web_price if > 0, otherwise returns retail_price."""
        if self.web_price and self.web_price > 0:
            return self.web_price
        return self.retail_price if self.retail_price else 0.0

    @property
    def selected_price(self) -> str:
        """Selects the minimum price from available prices.
        If web_price is null/zero, uses retail_price as web_price value."""
        # Use effective_web_price (web_price if available, otherwise retail_price)
        effective_web = self.effective_web_price
        prices = [p for p in [effective_web, self.map_price, self.retail_price] if p > 0]
        return str(min(prices)) if prices else "0.00"

    @property
    def shopify_title(self) -> str:
        """Generates a Shopify-compatible title (max 255 characters)."""
        SHOPIFY_TITLE_MAX = 255
        model_val = self.model if self.model else self.vendor_part_number
        base_title = f"{self.brand_name} {model_val}"
        
        # If base title already exceeds limit, truncate it
        if len(base_title) >= SHOPIFY_TITLE_MAX:
            return base_title[:SHOPIFY_TITLE_MAX]
        
        # Reserve space for " ..." if we need to truncate
        remaining = SHOPIFY_TITLE_MAX - len(base_title) - 4
        
        # If no description or not enough space, return base title
        if not self.description_short or remaining <= 0:
            return base_title
        
        # If description fits, append it
        if len(self.description_short) <= remaining:
            return f"{base_title} {self.description_short}"
        
        # Truncate description at word boundary and add ellipsis
        desc_snippet = self.description_short[:remaining].rsplit(' ', 1)[0]
        if desc_snippet:  # Only add if we have a snippet
            return f"{base_title} {desc_snippet}..."
        return base_title

    def get_sanitized_html(self) -> str:
        """Sanitizes HTML content, converting h2 tags to h3."""
        def clean(text):
            """Cleans HTML text by unescaping and replacing h2 with h3 tags."""
            if text is None:
                return ""
            decoded = html.unescape(text)
            # Replace opening <h2> tags with <h3>
            text = re.sub(r'<h2>', '<h3>', decoded, flags=re.I)
            # Replace closing </h2> tags with </h3>
            text = re.sub(r'</h2>', '</h3>', text, flags=re.I)
            return text
        
        sections = []
        # Only add description section if it exists
        if self.description_medium:
            sections.append(f"<h2>Description</h2>{clean(self.description_medium)}")
        if self.specifications_wysiwyg:
            sections.append(f"<h2>Tech Specs</h2>{clean(self.specifications_wysiwyg)}")
        return "".join(sections)
# ============================================================================
# End of models.py — Version: 1.3.0
# ============================================================================
