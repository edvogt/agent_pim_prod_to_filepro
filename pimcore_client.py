# ============================================================================
#  pimcore_client.py — Pimcore API Handler
#  Version: 1.1.4
# ============================================================================
import requests
import logging
import base64
from typing import List, Optional
from models import PimcoreProduct

logger = logging.getLogger(__name__)

class PimcoreClient:
    def __init__(self, base_url: str, endpoint_name: str, api_key: str):
        self.api_url = f"{base_url}/pimcore-graphql-webservices/{endpoint_name}?apikey={api_key}"
        self.session = requests.Session() #

    def fetch_products(self, prefix: str, limit: int = 5) -> List[PimcoreProduct]:
        query = """query($limit: Int, $filter: String) {
          getProdM06Listing(first: $limit, filter: $filter) {
            edges { node { id sku upc WebPrice MAP Retail BrandName Model VendorPartNumber 
                           Description_Medium Specifications_WYSIWYG WhatsInBox ProductType
                           ImagePrimary { id } } }
          }
        }"""
        filter_json = f'{{"PartPrefix":"{prefix}"}}'
        try:
            res = self.session.post(self.api_url, json={"query": query, "variables": {"limit": limit, "filter": filter_json}})
            nodes = res.json().get("data", {}).get("getProdM06Listing", {}).get("edges", [])
            return [PimcoreProduct(**item["node"]) for item in nodes]
        except Exception as e:
            logger.error(f"Pimcore fetch error: {e}")
            return []

    def get_asset_data(self, asset_id: str) -> Optional[bytes]:
        query = f"query {{ getAsset(id: {asset_id}) {{ data }} }}"
        try:
            res = self.session.post(self.api_url, json={"query": query})
            b64 = res.json().get("data", {}).get("getAsset", {}).get("data")
            return base64.b64decode(b64) if b64 else None
        except Exception as e:
            logger.error(f"Asset download error: {e}")
            return None
# ============================================================================
# End of pimcore_client.py — Version: 1.1.4
# ============================================================================
