# ============================================================================
#  models.py — Pydantic Data Models
#  Version: 1.1.3
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
    description_medium: str = Field("", alias="Description_Medium")
    specifications_wysiwyg: str = Field("", alias="Specifications_WYSIWYG")
    whats_in_box: str = Field("", alias="WhatsInBox")
    product_type_raw: Optional[str] = Field(None, alias="ProductType")
    image_asset_id: Optional[str] = None

    @property
    def selected_price(self) -> str:
        prices = [p for p in [self.web_price, self.map_price, self.retail_price] if p > 0]
        return str(min(prices)) if prices else "0.00"

    @property
    def shopify_title(self) -> str:
        model_val = self.model if self.model else self.vendor_part_number
        base_title = f"{self.brand_name} {model_val}"
        remaining = 147 - len(base_title)
        desc_snippet = self.description_medium[:remaining].rsplit(' ', 1)[0]
        return f"{base_title} {desc_snippet}...".strip()

    def get_sanitized_html(self) -> str:
        def clean(text):
            decoded = html.unescape(text) #
            return re.sub(r'</?h2>', lambda m: '<h3>' if '<h2' in m.group() else '</h3>', decoded, flags=re.I)
        sections = [f"<h2>Description</h2>{clean(self.description_medium)}"]
        if self.specifications_wysiwyg:
            sections.append(f"<h2>Tech Specs</h2>{clean(self.specifications_wysiwyg)}")
        return "".join(sections)
# ============================================================================
# End of models.py — Version: 1.1.3
# ============================================================================
